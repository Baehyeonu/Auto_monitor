"""
SQLite(students.db)의 데이터를 Railway Postgres로 이관하는 스크립트

실행 전 준비 사항
1. Railway에서 Postgres 서비스를 생성하고 Auto_monitor 서비스에 연결
2. Auto_monitor 서비스 Variables에 DATABASE_URL 추가
3. 로컬에서 `pip install asyncpg` (requirements.txt에도 포함되어 있어야 함)
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.engine import make_url
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", str(project_root / "students.db"))
SQLITE_URL = f"sqlite+aiosqlite:///{SQLITE_DB_PATH}"
POSTGRES_URL = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")

TABLES = ["students"]  # 현재 스키마는 학생 테이블만 존재
BOOL_FIELDS = {"is_cam_on", "is_absent", "is_admin"}
DATETIME_FIELDS = {
    "last_status_change",
    "last_alert_sent",
    "response_time",
    "last_leave_time",
    "last_absent_alert",
    "last_leave_admin_alert",
    "last_return_request_time",
    "created_at",
    "updated_at",
}


async def fetch_all_rows(engine, table: str) -> List[Dict[str, Any]]:
    async with engine.connect() as conn:
        result = await conn.execute(text(f"SELECT * FROM {table}"))
        raw_rows = [dict(row._mapping) for row in result]

    converted: List[Dict[str, Any]] = []
    for row in raw_rows:
        new_row = {}
        for key, value in row.items():
            if key in BOOL_FIELDS and value is not None:
                new_row[key] = bool(value)
            elif key in DATETIME_FIELDS and value:
                if isinstance(value, str):
                    try:
                        new_row[key] = datetime.fromisoformat(value)
                    except ValueError:
                        try:
                            new_row[key] = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                        except ValueError:
                            new_row[key] = value
                else:
                    new_row[key] = value
            else:
                new_row[key] = value
        converted.append(new_row)
    return converted


async def truncate_table(engine, table: str):
    async with engine.begin() as conn:
        if POSTGRES_URL and POSTGRES_URL.startswith("postgresql"):
            await conn.execute(text(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE'))
        else:
            await conn.execute(text(f'DELETE FROM "{table}"'))


async def insert_rows(engine, table: str, rows: List[Dict[str, Any]]):
    if not rows:
        return

    columns = rows[0].keys()
    placeholders = ", ".join(f":{col}" for col in columns)
    column_list = ", ".join(f'"{col}"' for col in columns)
    stmt = text(f'INSERT INTO "{table}" ({column_list}) VALUES ({placeholders})')

    async with engine.begin() as conn:
        await conn.execute(stmt, rows)


async def reset_sequence(engine, table: str, pk: str = "id"):
    url = make_url(POSTGRES_URL)
    if not url.drivername.startswith("postgresql"):
        return

    seq_sql = text(
        "SELECT setval(pg_get_serial_sequence(:table, :pk), "
        "(SELECT COALESCE(MAX({pk}), 1) FROM {table}))".format(table=table, pk=pk)
    )
    async with engine.begin() as conn:
        await conn.execute(seq_sql, {"table": table, "pk": pk})


async def migrate():
    if not POSTGRES_URL:
        raise RuntimeError("DATABASE_URL 환경변수를 찾을 수 없습니다. Postgres 연결 정보를 설정하세요.")

    print("=" * 60)
    print("🔄 SQLite -> Postgres 데이터 이관 시작")
    print("=" * 60)
    print(f"📁 SQLite 경로 : {SQLITE_DB_PATH}")
    print(f"🌐 Postgres URL: {POSTGRES_URL}")

    sqlite_engine = create_async_engine(SQLITE_URL, echo=False)
    postgres_engine = create_async_engine(POSTGRES_URL, echo=False)

    migrated_total = 0
    try:
        for table in TABLES:
            print(f"\n📦 테이블 처리: {table}")
            rows = await fetch_all_rows(sqlite_engine, table)
            print(f"   • SQLite 레코드 수: {len(rows)}")

            await truncate_table(postgres_engine, table)
            print("   • 대상 테이블 초기화 완료")

            await insert_rows(postgres_engine, table, rows)
            print("   • Postgres 적재 완료")
            await reset_sequence(postgres_engine, table)
            print("   • 시퀀스 위치 재조정 완료")
            migrated_total += len(rows)

    finally:
        await sqlite_engine.dispose()
        await postgres_engine.dispose()

    print("\n" + "=" * 60)
    print(f"✅ 마이그레이션 완료: 총 {migrated_total}건 전송")
    print("=" * 60)


async def main():
    try:
        await migrate()
    except Exception as e:
        print("\n❌ 마이그레이션 실패")
        print("=" * 60)
        print(e)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

