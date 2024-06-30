import sqlalchemy as sql
from sqlalchemy import orm

from organisations.comicvine import database


class Character(database.Base):
    __tablename__ = "characters"
    id = sql.Column(sql.Integer, primary_key=True, index=True)

    username = sql.Column(sql.String, unique=True, index=True)
    nickname = sql.Column(sql.String)

    comicvine_id = sql.Column(sql.Integer, index=True)

    gender = sql.Column(sql.Integer)
    summary = sql.Column(sql.String)
    powers = sql.Column(sql.String)
    date_of_birth = sql.Column(sql.String)

    image = sql.Column(sql.String)
    background_color = sql.Column(sql.String)

    posts = orm.relationship("Post", back_populates="owner")


class Post(database.Base):
    __tablename__ = "posts"
    id = sql.Column(sql.Integer, primary_key=True, index=True)
    owner_id = sql.Column(sql.Integer, sql.ForeignKey("characters.id"))

    content = sql.Column(sql.String)

    owner = orm.relationship("Character", back_populates="posts")
