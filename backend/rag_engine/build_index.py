"""构建知识库向量索引：python -m rag_engine.build_index（在 backend 目录执行）。"""

from .engine import RagEngine


def main() -> None:
    engine = RagEngine()
    data = engine.build()
    print(f"已索引 {data['count']} 个片段，维度 {data['dim']} -> {engine.index_path}")


if __name__ == "__main__":
    main()
