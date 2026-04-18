# STL
import uuid
import json

# External
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

# Custom
from database.make_db import get_session
from database.models import Strategy
from api.auth.dependencies import get_current_user
from api.auth.schemas import CurrentUser
from api.auth.repositories import get_user_by_email
from app_common.exceptions import NotFoundError
from .schemas import StrategyCreate, StrategyItem, StrategyDetail
from .repositories import create_strategy, get_strategies_by_user, get_strategy_by_id, update_strategy, delete_strategy

strategy_router = APIRouter(prefix="/strategies", tags=["Strategy endpoints"])


@strategy_router.post(
  path="",
  response_model=StrategyItem,
  status_code=status.HTTP_201_CREATED,
)
def save_strategy(
  payload: StrategyCreate,
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> StrategyItem:
  """Save a strategy graph for the current user."""
  user = get_user_by_email(session=session, email=current_user.email)
  if not user:
    raise NotFoundError(message="User not found")

  strategy = create_strategy(
    session=session,
    user_id=user.id,
    name=payload.name,
    graph_json=payload.graph_json,
  )
  return StrategyItem.model_validate(strategy)


@strategy_router.get(
  path="",
  response_model=list[StrategyItem],
  status_code=status.HTTP_200_OK,
)
def list_strategies(
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> list[StrategyItem]:
  """List all saved strategies for the current user."""
  user = get_user_by_email(session=session, email=current_user.email)
  if not user:
    raise NotFoundError(message="User not found")

  strategies: list[Strategy] = get_strategies_by_user(session=session, user_id=user.id)
  return [StrategyItem.model_validate(s) for s in strategies]


@strategy_router.get(
  path="/{strategy_id}",
  response_model=StrategyDetail,
  status_code=status.HTTP_200_OK,
)
def get_strategy(
  strategy_id: uuid.UUID,
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> StrategyDetail:
  """Get a single strategy with its full graph JSON."""
  user = get_user_by_email(session=session, email=current_user.email)
  if not user:
    raise NotFoundError(message="User not found")

  strategy: Strategy | None = get_strategy_by_id(session=session, strategy_id=strategy_id)
  if not strategy or strategy.user_id != user.id:
    raise NotFoundError(message="Strategy not found")

  return StrategyDetail(
    id=strategy.id,
    name=strategy.name,
    graph_json=json.loads(strategy.graph_json),
    created_at=strategy.created_at,
    updated_at=strategy.updated_at,
  )


@strategy_router.put(
  path="/{strategy_id}",
  response_model=StrategyItem,
  status_code=status.HTTP_200_OK,
)
def overwrite_strategy(
  strategy_id: uuid.UUID,
  payload: StrategyCreate,
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> StrategyItem:
  """Overwrite an existing strategy's name and graph."""
  user = get_user_by_email(session=session, email=current_user.email)
  if not user:
    raise NotFoundError(message="User not found")

  strategy: Strategy | None = get_strategy_by_id(session=session, strategy_id=strategy_id)
  if not strategy or strategy.user_id != user.id:
    raise NotFoundError(message="Strategy not found")

  updated = update_strategy(
    session=session,
    strategy=strategy,
    name=payload.name,
    graph_json=payload.graph_json,
  )
  return StrategyItem.model_validate(updated)


@strategy_router.delete(
  path="/{strategy_id}",
  status_code=status.HTTP_204_NO_CONTENT,
)
def remove_strategy(
  strategy_id: uuid.UUID,
  current_user: CurrentUser = Depends(get_current_user),
  session: Session = Depends(get_session),
) -> None:
  """Delete one of the current user's saved strategies."""
  user = get_user_by_email(session=session, email=current_user.email)
  if not user:
    raise NotFoundError(message="User not found")

  strategy: Strategy | None = get_strategy_by_id(session=session, strategy_id=strategy_id)
  if not strategy or strategy.user_id != user.id:
    raise NotFoundError(message="Strategy not found")

  delete_strategy(session=session, strategy=strategy)
