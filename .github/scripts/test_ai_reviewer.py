import os
import sys
from deepeval import evaluate
from deepeval.metrics import HallucinationMetric, GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.models.base_model import DeepEvalBaseLLM
import google.generativeai as genai

# Custom Gemini Judge for DeepEval
class GeminiJudge(DeepEvalBaseLLM):
    def __init__(self, model_name="gemini-1.5-flash-latest"):
        self.model_name = model_name

    def load_model(self):
        # Configure API key
        api_key = os.getenv("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
        return genai.GenerativeModel(self.model_name)

    def generate(self, prompt: str) -> str:
        model = self.load_model()
        res = model.generate_content(prompt)
        return res.text

    async def a_generate(self, prompt: str) -> str:
        model = self.load_model()
        res = await model.generate_content_async(prompt)
        return res.text

    def get_model_name(self):
        return self.model_name

def main():
    # Setup Judge Model (fallback to OpenAI if no Gemini key, or custom Gemini wrapper)
    judge_model = None
    if os.getenv("GEMINI_API_KEY"):
        print("Using Gemini as the Evaluation Judge Model...")
        judge_model = GeminiJudge(model_name="gemini-1.5-flash-latest")
    elif os.getenv("OPENAI_API_KEY"):
        print("Using OpenAI as the Evaluation Judge Model...")
        # DeepEval defaults to OpenAI if key is present
        judge_model = "gpt-4o"
    else:
        print("Error: Neither GEMINI_API_KEY nor OPENAI_API_KEY was found in environment.", file=sys.stderr)
        sys.exit(1)

    # 1. Correctness Metric (G-Eval)
    correctness_metric = GEval(
        name="Correctness",
        criteria="Determine whether the actual code review accurately identifies the bugs and aligns with the expected human-written review.",
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
        threshold=0.7,
        model=judge_model
    )

    # 2. Hallucination Metric
    hallucination_metric = HallucinationMetric(
        threshold=0.5,
        model=judge_model
    )

    # 3. Define Test Cases
    test_cases = [
        # Case 1: Bad Dart Code (Undefined variable)
        LLMTestCase(
            input="void main() { print(userName); }",
            actual_output="The code has a compilation error because 'userName' is undefined. Also, this will cause a memory leak in Firebase Cloud Firestore.",
            expected_output="The code will fail to compile because the variable 'userName' is not declared or defined anywhere.",
            context=["This is a simple Dart console application. The variable 'userName' is not declared. It does not use Firebase, Cloud Firestore, or any external database."]
        ),
        # Case 2: Good Python Code
        LLMTestCase(
            input="def add(a: int, b: int) -> int:\n    return a + b",
            actual_output="This code looks clean and correct. It has proper type hinting and correctly returns the sum of two integers.",
            expected_output="The code is correct, well-structured, and has appropriate type annotations.",
            context=["This is a standard Python helper function to sum two integers. There are no bugs or performance issues."]
        ),
        # Case 3: Bad Python Code (Mutable Default Argument)
        LLMTestCase(
            input="def append_to(element, target=[]):\n    target.append(element)\n    return target",
            actual_output="This code has a potential bug because it uses a mutable default argument (`target=[]`). The same list instance will be shared across calls.",
            expected_output="Using a mutable default argument `target=[]` will cause unexpected behavior because the list persists across multiple function calls.",
            context=["This Python function demonstrates the mutable default argument trap. The correct implementation should default `target` to `None` and instantiate a new list if `target is None`."]
        )
    ]

    print(f"Running evaluation on {len(test_cases)} test cases...\n")
    results = evaluate(test_cases, [correctness_metric, hallucination_metric])
    
    print("\nDeepEval Evaluation Finished successfully!")

if __name__ == "__main__":
    main()
