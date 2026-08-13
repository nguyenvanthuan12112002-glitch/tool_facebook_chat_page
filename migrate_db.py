from backend.database import engine, Base
from backend.models import PushSubscription

print("Creating push subscriptions table...")
Base.metadata.create_all(bind=engine)
print("Done!")
