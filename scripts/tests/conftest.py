"""모듈 import 전 필수 환경변수 설정"""
import os

# notion_to_md.py는 모듈 로드 시 이 값들을 os.environ[] 으로 읽음
os.environ.setdefault("NOTION_TOKEN", "test-token")
os.environ.setdefault("NOTION_DATABASE_ID", "test-database-id")
os.environ.setdefault("SAVE_DIR", "docs/guide")
