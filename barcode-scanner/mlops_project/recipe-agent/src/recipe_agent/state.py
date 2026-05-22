from typing import TypedDict, Optional, List, Annotated
from langchain_core.messages import BaseMessage
import operator

class AgentState(TypedDict):
    """Состояние агента."""
    messages: Annotated[List[BaseMessage], operator.add]
    active_collection_id: Optional[int]
    active_recipe_id: Optional[int]