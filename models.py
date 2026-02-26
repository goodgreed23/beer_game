from utils.prompt_utils import qualitative_beergame_prompt, quantitative_beergame_prompt


MODEL_CONFIGS = {
    "BeerGameQualitative": {
        "name": "Beer Game qualitative coach",
        "prompt": qualitative_beergame_prompt,
        "uses_rag": False,
        "uses_classification": False,
    },
    "BeerGameQuantitative": {
        "name": "Beer Game quantitative coach",
        "prompt": quantitative_beergame_prompt,
        "uses_rag": False,
        "uses_classification": False,
    },
}
