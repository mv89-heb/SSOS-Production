# מחסן ומלאי

`/dashboard/inventory` is the shared warehouse workflow for mobile and desktop.

- Mobile: search/select a product, enter the physical count, and save.
- The save creates a `count` inventory movement and updates `current_stock` through the existing inventory planning API.
- Desktop: the same screen shows current stock and demand-based recommendations.
- No stock is fabricated. Recommendations remain `insufficient_data` until enough real stock checks exist.
