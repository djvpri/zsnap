from datetime import datetime, timedelta

def calculate_expiry(plan: str):
    now = datetime.now()

    if plan == "daily":
        return now + timedelta(days=1)
    elif plan == "weekly":
        return now + timedelta(days=7)
    elif plan == "monthly":
        return now + timedelta(days=30)
    elif plan == "yearly":
        return now + timedelta(days=365)
    return None