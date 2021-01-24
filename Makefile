
create-migrations:
	alembic revision --autogenerate

upgrade:
	alembic upgrade head
