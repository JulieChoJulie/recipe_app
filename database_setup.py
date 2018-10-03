import sys
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

Base = declarative_base()

class User(Base):
    __tablename__ = 'user'

    id = Column(Integer, primary_key=True)
    name = Column(String(250), nullable=False)
    email = Column(String(250))
    picture = Column(String(250))

class Category(Base):
    __tablename__ = 'category'
    id = Column(Integer, primary_key = True)
    name = Column(String(80), nullable = False)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

class Menu(Base):
    __tablename__ = 'menu'
    id = Column(Integer, primary_key = True)
    name = Column(String(80), nullable = False)
    picture = Column(String(250))
    servings = Column(Integer)
    calories = Column(Integer)
    hour = Column(Integer)
    minute = Column(Integer)
    category_id = Column(Integer, ForeignKey('category.id'))
    category = relationship(Category)
    user_id = Column(Integer, ForeignKey('user.id'))
    user = relationship(User)

class Ingredient(Base):
    __tablename__ = 'ingredient'
    id = Column(Integer, primary_key = True)
    amount = Column(String(50))
    description =  Column(String(80))
    menu_id = Column(Integer, ForeignKey('menu.id'))
    menu = relationship(Menu)

class Direction(Base):
    __tablename__ = 'direction'
    id = Column(Integer, primary_key = True)
    direction = Column(String(350))
    menu_id = Column(Integer, ForeignKey('menu.id'))
    menu = relationship(Menu)

engine = create_engine('sqlite:///recipes.db')
Base.metadata.create_all(engine)