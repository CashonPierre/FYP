# STL
import uuid
import json
from datetime import datetime, timezone

# External
from sqlalchemy.orm import Session
from sqlalchemy import select

# Custom
from database.models import Strategy


def create_strategy(
  session: Session,
  user_id: uuid.UUID,
  name: str,
  graph_json: dict,
) -> Strategy:
  strategy = Strategy(
    user_id=user_id,
    name=name,
    graph_json=json.dumps(graph_json),
  )
  session.add(strategy)
  session.flush()
  return strategy


def get_strategies_by_user(session: Session, user_id: uuid.UUID) -> list[Strategy]:
  statement = (
    select(Strategy)
    .where(Strategy.user_id == user_id)
    .order_by(Strategy.updated_at.desc())
  )
  return list(session.execute(statement).scalars().all())


def get_strategy_by_id(session: Session, strategy_id: uuid.UUID) -> Strategy | None:
  statement = select(Strategy).where(Strategy.id == strategy_id)
  return session.execute(statement).scalar_one_or_none()


def update_strategy(
  session: Session,
  strategy: Strategy,
  name: str,
  graph_json: dict,
) -> Strategy:
  strategy.name = name
  strategy.graph_json = json.dumps(graph_json)
  strategy.updated_at = datetime.now(timezone.utc)
  session.flush()
  return strategy
