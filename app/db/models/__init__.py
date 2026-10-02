"""模型注册入口，初始为空。

新增模型继承 app.db.base.Base，并在这里显式导入，例如 from .item import Item。
被导入的模型才会注册到 Base.metadata；Alembic 使用这些元数据生成迁移。
这里仅注册模型，不执行建表、查询或初始化数据。
"""
