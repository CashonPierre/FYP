# External
from fastapi import APIRouter, Depends, status

# Custom
from api.auth.dependencies import get_current_user
from api.auth.schemas import CurrentUser
from .schemas import BuildGraphRequest, BuildGraphResponse
from .service import build_graph_from_prompt


ai_router = APIRouter(prefix="/ai", tags=["AI graph builder"])


@ai_router.post(
  path="/build-graph",
  response_model=BuildGraphResponse,
  status_code=status.HTTP_200_OK,
)
def build_graph(
  payload: BuildGraphRequest,
  _current_user: CurrentUser = Depends(get_current_user),
) -> BuildGraphResponse:
  """Translate a natural-language trading idea into a runnable node graph.

  Requires a valid auth token — the feature costs money per call and we
  don't want anonymous traffic burning through the OpenRouter budget."""
  return build_graph_from_prompt(payload.prompt)
