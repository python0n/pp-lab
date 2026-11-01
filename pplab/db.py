import pymysql
import pymysql.cursors

from . import config

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS pplab_runs (
        variant VARCHAR(32) NOT NULL,
        mode TINYINT NOT NULL,
        started_at DATETIME NOT NULL,
        finished_at DATETIME NULL,
        scores INT NOT NULL DEFAULT 0,
        errors INT NOT NULL DEFAULT 0,
        PRIMARY KEY (variant, mode)
    )""",
    """CREATE TABLE IF NOT EXISTS pplab_scores (
        variant VARCHAR(32) NOT NULL,
        score_id BIGINT NOT NULL,
        user_id INT NOT NULL,
        map_md5 CHAR(32) NOT NULL,
        mode TINYINT NOT NULL,
        pp FLOAT NOT NULL,
        stars FLOAT NOT NULL,
        aim FLOAT NOT NULL,
        speed FLOAT NOT NULL,
        acc_pp FLOAT NOT NULL,
        fl FLOAT NOT NULL,
        reading FLOAT NOT NULL,
        PRIMARY KEY (variant, score_id),
        KEY pplab_scores_user (variant, mode, user_id)
    )""",
    """CREATE TABLE IF NOT EXISTS pplab_players (
        variant VARCHAR(32) NOT NULL,
        mode TINYINT NOT NULL,
        user_id INT NOT NULL,
        pp FLOAT NOT NULL,
        plays INT NOT NULL,
        `rank` INT NOT NULL,
        PRIMARY KEY (variant, mode, user_id),
        KEY pplab_players_rank (variant, mode, `rank`)
    )""",
]


def connect():
    return pymysql.connect(
        **config.DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        connect_timeout=5,
    )


def ensure_schema(conn) -> None:
    with conn.cursor() as cur:
        for stmt in SCHEMA:
            cur.execute(stmt)
