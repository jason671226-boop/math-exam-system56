import unittest

from math_output import render_math_markdown, split_math_segments
from services.g8_question_service import format_question_set, local_question_bank


class SharedMathRendererTests(unittest.TestCase):
    def test_common_notation_is_wrapped_for_streamlit_math(self):
        rendered = render_math_markdown(
            r"(4x+1)(4x-1) = 16x^2-1; \frac{1}{2}; \sqrt{3}; x^2+y^2=z^2"
        )
        self.assertIn("$(4x+1)(4x-1) = 16x^2-1$", rendered)
        self.assertIn(r"$\frac{1}{2}$", rendered)
        self.assertIn(r"$\sqrt{3}$", rendered)
        self.assertNotIn(r"\frac{1}{2}", rendered.replace(r"$\frac{1}{2}$", ""))

    def test_local_exam_is_separated_into_question_answer_solution(self):
        rendered = format_question_set(local_question_bank()[:1])
        self.assertIn("### 第 1 題", rendered)
        self.assertIn("題目：", rendered)
        self.assertIn("**答案：**", rendered)
        self.assertIn("**詳解：**", rendered)

    def test_high_school_inline_formula_keeps_sentence_and_options_together(self):
        for grade, text in (
            (10, r"G10：若 \(f(x)=x^2+1\)，則 A. \(f(1)=2\) B. \(f(1)=1\)"),
            (11, r"G11：設 \(\sin\theta=\frac{1}{2}\)，選 A. \(\theta=30^\circ\) B. \(\theta=60^\circ\)"),
            (12, r"G12：若 \(f'(x)=2x\)，則 A. \(f'(2)=4\) B. \(f'(2)=2\)"),
        ):
            with self.subTest(grade=grade):
                rendered = render_math_markdown(text)
                self.assertNotIn("$$", rendered)
                self.assertIn(" A. $", rendered)
                self.assertIn(" B. $", rendered)
                self.assertEqual(sum(is_math for is_math, _ in split_math_segments(text)), 3)

    def test_only_long_bracket_formula_stays_block_math(self):
        short = render_math_markdown(r"若 \[x^2+1=2\]，求 x。")
        long_formula = " + ".join(f"x_{{{index}}}" for index in range(30))
        long = render_math_markdown(r"計算 \[" + long_formula + r"\]")
        self.assertNotIn("$$", short)
        self.assertIn("$x^2+1=2$", short)
        self.assertIn("$$", long)


if __name__ == "__main__":
    unittest.main()
