"""
batch/quality_metrics_dto.py
データ転送オブジェクトを定義して品質メトリクスの構造を明確に
"""



class QualityMetrics:
    """品質メトリクスを保持するデータクラス"""

    def __init__(
        self,
        total: int,
        prefecture_counts: dict[str, int],
        missing_score: int,
        missing_prefecture: int,
        missing_address: int,
        duplicates: list[dict[str, str]],
    ):
        self.total = total
        self.prefecture_counts = prefecture_counts
        self.missing_score = missing_score
        self.missing_prefecture = missing_prefecture
        self.missing_address = missing_address
        self.duplicates = duplicates


class SQLiteMetrics:
    """SQLiteメトリクスを保持するデータクラス"""

    def __init__(
        self, total: int, scored: int, public_toilets: int, prefecture_counts: dict[str, int], metadata: dict[str, str]
    ):
        self.total = total
        self.scored = scored
        self.public_toilets = public_toilets
        self.prefecture_counts = prefecture_counts
        self.metadata = metadata


class ComparisonResult:
    """メトリクス比較結果を保持するデータクラス"""

    def __init__(self, errors: list[str], warnings: list[str]):
        self.errors = errors
        self.warnings = warnings


class QualityGateResult:
    """品質ゲート評価結果を保持するデータクラス"""

    def __init__(self, errors: list[str], warnings: list[str]):
        self.errors = errors
        self.warnings = warnings
