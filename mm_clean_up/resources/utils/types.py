from typing import Tuple, Any, TypedDict

class Icon(TypedDict):
    name: str
    url: str
    freepik_id: int

class PositionedIcon(Icon):
    id: str
    coord: Tuple[int] 


class FullPositionedIcon(PositionedIcon):
    img: str
