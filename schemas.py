import pydantic as pydantic


class _UserBase(pydantic.BaseModel):
    email: str
    password_hash: str
    username: str


class UserCreate(_UserBase):

    class Config:
        from_attributes = True


class User(_UserBase):
    id: int

    class Config:
        from_attributes = True


class UserUpdate(_UserBase):
    email: str = None
    password_hash: str = None
    username: str = None

    new_password: str = None

    class Config:
        from_attributes = True


# ------------------------------------------------- #


class _PostBase(pydantic.BaseModel):
    content: str


class Post(_PostBase):
    id: int
    owner_id: int

    class Config:
        from_attributes = True


# ------------------------------------------------- #


class _BotBase(pydantic.BaseModel):
    username: str
    nickname: str
    image: str
    background_color: str


class Bot(_BotBase):
    id: int
    owner_id: int

    class Config:
        from_attributes = True


# ------------------------------------------------- #


class _TagBase(pydantic.BaseModel):
    name: str


class Tag(_TagBase):
    id: int

    class Config:
        from_attributes = True


# ------------------------------------------------- #

class _Info(pydantic.BaseModel):
    id: int


class PostInfo(_Info):
    favorite: bool | None

    favorite_count: int


class FavoriteCount(_Info):
    favorite_count: int


class BotInfo(_Info):
    following: bool | None

    post_count: int
    favorites_count: int
    followers_count: int
    mentioned_count: int


class TagInfo(_Info):
    following: bool | None

    post_count: int
    follower_count: int


class FollowingCount(_Info):
    following_count: int
