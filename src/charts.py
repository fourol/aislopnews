"""Chart generator for visualizing market intelligence digests."""
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt


class ChartGenerator:
    def __init__(self, output_dir: str = "data/charts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_digest_chart(
        self,
        topic_counts: Dict[str, int],
        competitor_counts: Dict[str, int],
    ) -> Optional[str]:
        """Generates a modern dual-panel chart (Topics + Competitors activity)."""
        if not topic_counts and not competitor_counts:
            return None

        # Clean empty values
        topic_counts = {k: v for k, v in topic_counts.items() if v > 0}
        competitor_counts = {k: v for k, v in competitor_counts.items() if v > 0}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chart_path = self.output_dir / f"chart_{timestamp}.png"

        # Theme settings
        bg_color = "#181825"
        card_color = "#1e1e2e"
        text_color = "#cdd6f4"
        accent_palette = ["#89b4fa", "#a6e3a1", "#fab387", "#f38ba8", "#cba6f7", "#94e2d5"]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5), facecolor=bg_color)
        fig.suptitle("Аналитический срез: ИИ, Web3, Игры и Технологии", fontsize=15, color=text_color, fontweight="bold", y=0.98)

        # Panel 1: Topics Distribution
        ax1.set_facecolor(card_color)
        if topic_counts:
            topics = list(topic_counts.keys())
            counts = list(topic_counts.values())
            colors = [accent_palette[i % len(accent_palette)] for i in range(len(topics))]

            bars = ax1.barh(topics, counts, color=colors, height=0.6)
            ax1.set_title("Тематика событий", color=text_color, fontsize=12, pad=10)
            ax1.tick_params(colors=text_color, labelsize=10)
            ax1.invert_yaxis()  # Top down
            for spine in ax1.spines.values():
                spine.set_color("#313244")
            ax1.xaxis.grid(True, linestyle="--", alpha=0.3, color="#585b70")

            # Value labels on bars
            for bar in bars:
                w = bar.get_width()
                ax1.text(w + 0.1, bar.get_y() + bar.get_height() / 2, f"{int(w)}",
                         ha="left", va="center", color=text_color, fontsize=10, fontweight="bold")
        else:
            ax1.text(0.5, 0.5, "Нет данных по направлениям", color=text_color, ha="center", va="center")
            ax1.axis("off")

        # Panel 2: Competitor/Source mentions
        ax2.set_facecolor(card_color)
        if competitor_counts:
            comps = list(competitor_counts.keys())
            c_counts = list(competitor_counts.values())
            c_colors = [accent_palette[(i + 2) % len(accent_palette)] for i in range(len(comps))]

            bars = ax2.barh(comps, c_counts, color=c_colors, height=0.6)
            ax2.set_title("Активность источников и платформ", color=text_color, fontsize=12, pad=10)
            ax2.tick_params(colors=text_color, labelsize=10)
            ax2.invert_yaxis()
            for spine in ax2.spines.values():
                spine.set_color("#313244")
            ax2.xaxis.grid(True, linestyle="--", alpha=0.3, color="#585b70")

            for bar in bars:
                w = bar.get_width()
                ax2.text(w + 0.1, bar.get_y() + bar.get_height() / 2, f"{int(w)}",
                         ha="left", va="center", color=text_color, fontsize=10, fontweight="bold")
        else:
            ax2.text(0.5, 0.5, "Нет данных по конкурентам", color=text_color, ha="center", va="center")
            ax2.axis("off")

        plt.tight_layout()
        plt.subplots_adjust(top=0.85)
        plt.savefig(chart_path, dpi=200, bbox_inches="tight", facecolor=bg_color)
        plt.close(fig)

        return str(chart_path)
