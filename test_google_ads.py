import os
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

# Customer ID (without hyphens)
CUSTOMER_ID = "6549489566"

def get_yesterday_spend():
    try:
        # Load credentials from yaml
        script_dir = os.path.dirname(os.path.abspath(__file__))
        yaml_path = os.path.join(script_dir, "google_ads.yaml")
        client = GoogleAdsClient.load_from_storage(yaml_path)

        ga_service = client.get_service("GoogleAdsService")

        # Query: Get campaign name and cost for yesterday
        query = """
            SELECT 
                campaign.name, 
                metrics.cost_micros 
            FROM campaign 
            WHERE segments.date DURING YESTERDAY
              AND metrics.cost_micros > 0
        """

        response = ga_service.search(customer_id=CUSTOMER_ID, query=query)

        # Categorize costs
        costs = {
            "family": 0,
            "general": 0,
            "nri": 0,
            "unknown": 0
        }

        total_cost = 0

        for row in response:
            campaign_name = row.campaign.name.lower()
            # Convert micros to currency (1,000,000 micros = 1 currency unit)
            cost = row.metrics.cost_micros / 1000000.0

            total_cost += cost

            if "family" in campaign_name:
                costs["family"] += cost
            elif "general" in campaign_name:
                costs["general"] += cost
            elif "nri" in campaign_name:
                costs["nri"] += cost
            else:
                costs["unknown"] += cost

        # Round all costs
        for k in costs:
            costs[k] = round(costs[k])
        
        costs["total"] = round(total_cost)

        return costs

    except GoogleAdsException as ex:
        print(f"Google Ads API Error: {ex}")
        for error in ex.failure.errors:
            print(f"\tError with message: {error.message}.")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None

if __name__ == "__main__":
    print("Testing Google Ads API connection for YESTERDAY's spend...")
    spend = get_yesterday_spend()
    if spend:
        print("Successfully fetched spend:")
        print(spend)
    else:
        print("Failed to fetch spend.")
