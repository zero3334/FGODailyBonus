"""FGO JP friendship pool and ticket shop selection.

Behavior adapted from DNNDHH/F-D-L (license not declared in that repository).
"""


def friend_pool(catalog, now):
    """Match F-D-L GetGachaSubIdFP: choose highest-priority open entry."""
    best = None
    if not isinstance(catalog, list):
        return None
    for row in catalog:
        try:
            if int(row['openedAt']) <= now <= int(row['closedAt']):
                candidate = (int(row['priority']), int(row['id']))
                if best is None or candidate[0] > best[0]:
                    best = candidate
        except (KeyError, TypeError, ValueError):
            continue
    return str(best[1]) if best is not None else None


LIMITED_FRIEND_POOLS = (
    ('20', '8'), ('21', '8'), ('22', '4'),
    ('23', '4'), ('24', '2'), ('25', '2'),
)


def ticket_orders(catalog, user_shops, mana, now):
    """Return current monthly/event ticket orders, bounded by prism balance."""
    if not isinstance(catalog, list) or not isinstance(user_shops, list):
        return []
    try:
        bought = {int(x['shopId']): int(x['num']) for x in user_shops
                  if isinstance(x, dict) and 'shopId' in x and 'num' in x}
        remaining = max(0, int(mana))
    except (KeyError, ValueError, TypeError):
        return []
    result = []
    seen = set()
    for flag, label in ((4096, '每月'), (2048, '活动')):
        options = []
        for row in catalog:
            try:
                sid = int(row['baseShopId'])
                prices = row['prices']
                if (sid in seen or int(row['flag']) != flag or row['targetIds'] != [4001]
                    or int(row['payType']) != 4 or int(row['shopType']) != 2
                    or not int(row['openedAt']) <= now < int(row['closedAt'])
                    or not isinstance(prices, list) or len(prices) != 1):
                    continue
                price = int(prices[0])
                limit = int(row['limitNum'])
                count = bought.get(sid, 0)
                if price <= 0 or limit <= 0 or not 0 <= count <= limit:
                    continue
                options.append((sid, price, limit - count))
            except (KeyError, ValueError, TypeError):
                continue
        # Multiple active matches could represent a different shop; never guess by max ID.
        if len(options) != 1:
            continue
        sid, price, capacity = options[0]
        qty = min(capacity, remaining // price)
        if qty > 0:
            result.append((label, sid, qty, qty * price))
            remaining -= qty * price
            seen.add(sid)
    return result
