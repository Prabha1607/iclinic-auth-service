from pydantic import BaseModel


class RoleResponse(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}