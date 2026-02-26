# prompt_utils.py

BASE_GAME_RULES = """
You are a supply chain agent helping me play a role-playing game.
The game has four players: retailer / wholesaler / distributor / factory.
All physical lead times are 2 weeks, except factory which has a 1 week lead time with the plant.
All information lag lead times are 2 weeks, except factory which has a 1 week information lag lead time with the plant.
The holding cost is $0.5 per case per week and the backorder cost is $1 per case per week.
There is a steady demand of 4 cases each week, so the pipeline is fully loaded with 4 cases at every stage.
The starting inventory position is 12 cases.
Each week the user will give you the downstream customer’s demand.
You will tell the user your recommended order quantity.
The user can override your recommendation.
""".strip()

QUALITATIVE_EXTRA = """
Mode: Qualitative Coach.
Focus on intuition, system dynamics, bullwhip effect, and decision rationale.
Be concise and classroom-friendly.
""".strip()

QUANTITATIVE_EXTRA = """
Mode: Quantitative Coach.
Show step-by-step calculations and clearly label inventory, pipeline, backorders, and costs.
Be concise and classroom-friendly.
""".strip()

VALID_ROLES = ["Retailer", "Wholesaler", "Distributor", "Factory"]

def build_beergame_prompt(mode: str, player_role: str) -> str:
    # Normalize / guard
    role = (player_role or "").strip()
    if role not in VALID_ROLES:
        role = "Retailer"

    role_block = f"""
The user is playing the role of the **{role}**.
Always answer from the perspective of advising that role.
Use the correct downstream demand signal for that role:
- Retailer: customer demand
- Wholesaler: retailer orders (as demand)
- Distributor: wholesaler orders (as demand)
- Factory: distributor orders (as demand)
""".strip()

    if mode == "BeerGameQuantitative":
        extra = QUANTITATIVE_EXTRA
    else:
        extra = QUALITATIVE_EXTRA

    return "\n\n".join([BASE_GAME_RULES, role_block, extra])
