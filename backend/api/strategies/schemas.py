# STL
import uuid
from datetime import datetime

# External
from pydantic import BaseModel


class StrategyCreate(BaseModel):
  name: str
  graph_json: dict


class StrategyItem(BaseModel):
  id: uuid.UUID
  name: str
  created_at: datetime
  updated_at: datetime

  model_config = {"from_attributes": True}


class StrategyDetail(BaseModel):
  id: uuid.UUID
  name: str
  graph_json: dict
  created_at: datetime
  updated_at: datetime

  model_config = {"from_attributes": True}
