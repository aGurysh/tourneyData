from typing import Annotated

from fastapi import Path, Query

Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]
TournamentId = Annotated[int, Path(gt=0)]
OptionalId = Annotated[int | None, Query(gt=0)]
