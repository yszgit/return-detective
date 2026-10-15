from .config import ROOT, SNAPSHOT_DATE, aws_settings
from .data import cohort_rates, evidence, records


def investigate(sku, as_of=SNAPSHOT_DATE):
    """Optional live read-only investigation; requires team AWS credentials."""
    import boto3
    from strands import Agent, tool
    from strands.models import BedrockModel

    region, model_id = aws_settings()

    @tool
    def query_cohorts() -> list:
        """Get sales-adjusted cohort rates for the requested SKU and as-of date."""
        return cohort_rates(sku, as_of)

    @tool
    def query_returns() -> list:
        """Read up to 100 observed returns with record IDs for this SKU."""
        return evidence("returns", sku, as_of)

    @tool
    def query_reviews() -> list:
        """Read up to 100 product reviews observed by the as-of date."""
        return evidence("reviews", sku, as_of)

    @tool
    def query_inventory() -> list:
        """Read the synthetic inventory snapshot and cohort mapping for this SKU."""
        if as_of != SNAPSHOT_DATE:
            return [{"status": "unavailable", "reason": "No inventory snapshot for this as-of date"}]
        return [r for r in records("inventory") if r["sku"] == sku]

    model = BedrockModel(model_id=model_id,
                         boto_session=boto3.Session(region_name=region),
                         temperature=0, max_tokens=1500)
    agent = Agent(model=model,
                  tools=[query_cohorts, query_returns, query_reviews, query_inventory],
                  system_prompt=(ROOT / "prompts" / "investigator.txt").read_text(encoding="utf-8"))
    return str(agent(f"Investigate SKU {sku}; as-of date {as_of}. All records are synthetic."))
