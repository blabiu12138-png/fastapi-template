from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有新项目 ORM 模型继承的声明式基类，不预设主键和业务字段。"""
