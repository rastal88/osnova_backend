# Osnova (backend)

### Description

A template for speeding up the development of web applications. Backend part


### Install

1. Clone repository
2. Install python 3.13.2 
3. Install requirements
4. Install postgres

### First run

1. Create a database, connect to it and set an extension:
```sql
\c <db_name>
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```
2. Create .env and заполните своими данными по образцу из .env.example 
3. Обновите базу данных

```bash
alembic revision --autogenerate -m "<info_massege>"
alembic upgrade head
```

4. 
### Run 
```bash
python run.py --host <host> --port <port>
# or
./run.sh -h <host> -p <port>
```