import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta
import os

# Set seed for reproducibility
np.random.seed(42)
random.seed(42)

def generate_data():
    base_dir = "/Users/itsarifworld/Desktop/Placements/projectsssssssss/business/business-intelligence-ai/data"
    
    # 1. SALES DATA
    dates = pd.date_range(start='2026-07-01', end='2026-08-27')
    regions = ['North', 'South', 'East', 'West']
    products = ['XPhone Pro', 'TabMax', 'NovaWatch']
    
    sales_data = []
    
    for date in dates:
        for region in regions:
            for product in products:
                # NovaWatch only from Aug 16
                if product == 'NovaWatch' and date < pd.Timestamp('2026-08-16'):
                    continue
                
                # Base values
                if product == 'XPhone Pro':
                    price = 50000
                    units_base = 50
                    orders_base = 45
                elif product == 'TabMax':
                    price = 35000
                    units_base = 40
                    orders_base = 35
                else: # NovaWatch
                    price = 25000
                    units_base = 20
                    orders_base = 18
                
                # Random variation (±5%)
                var_multiplier = 1 + np.random.uniform(-0.05, 0.05)
                units = int(units_base * var_multiplier)
                orders = int(orders_base * var_multiplier)
                
                # Scenarios
                # Current period: Aug 21-27
                is_current = pd.Timestamp('2026-08-21') <= date <= pd.Timestamp('2026-08-27')
                
                if is_current:
                    # South + XPhone Pro scenario
                    if region == 'South' and product == 'XPhone Pro':
                        price = 47500
                        units = int(42 * var_multiplier)
                        orders = int(37 * var_multiplier)
                    
                    # East + TabMax scenario
                    elif region == 'East' and product == 'TabMax':
                        # ~8% drop in revenue -> slightly lower units
                        units = int(units_base * 0.92 * var_multiplier)
                        orders = int(orders_base * 0.92 * var_multiplier)
                    
                    # General slight growth for others
                    elif not (region == 'South' and product == 'XPhone Pro') and not (region == 'East' and product == 'TabMax'):
                        growth = 1 + np.random.uniform(0.01, 0.03)
                        units = int(units * growth)
                        orders = int(orders * growth)
                
                revenue = units * price
                
                sales_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'region': region,
                    'product': product,
                    'units': units,
                    'price': price,
                    'orders': orders,
                    'revenue': revenue
                })
                
    pd.DataFrame(sales_data).to_csv(os.path.join(base_dir, 'sales.csv'), index=False)
    
    # 2. MARKETING DATA
    mondays = pd.date_range(start='2026-07-01', end='2026-08-27', freq='W-MON')
    # If 2026-07-01 is not monday, date_range freq='W-MON' gets all mondays after. 
    # Let's explicitly just use Mondays.
    campaigns = ['Brand Awareness', 'Product Launch', 'Seasonal Sale', 'Performance']
    
    mkt_data = []
    
    for date in mondays:
        if date > pd.Timestamp('2026-08-27'):
            continue
            
        for region in regions:
            # East Low-confidence scenario: no marketing data for last 3 weeks (Aug 11, 18, 25)
            # Actually Mondys in Aug 2026: Aug 3, 10, 17, 24.
            # Let's drop if date >= Aug 10 for East to simulate missing last 3 weeks
            if region == 'East' and date >= pd.Timestamp('2026-08-10'):
                continue
                
            for product in products:
                if product == 'NovaWatch' and date < pd.Timestamp('2026-08-16'):
                    continue
                    
                campaign = np.random.choice(campaigns)
                
                if product == 'XPhone Pro':
                    spend = 500000
                    clicks = 5000
                    conversions = 250
                elif product == 'TabMax':
                    spend = 300000
                    clicks = 3000
                    conversions = 150
                else: # NovaWatch
                    spend = 200000
                    clicks = 2000
                    conversions = 100
                
                # South XPhone Pro scenario
                if region == 'South' and product == 'XPhone Pro' and date >= pd.Timestamp('2026-08-17'):
                    spend = int(325000)
                    clicks = int(clicks * 0.65)
                    conversions = int(conversions * 0.5)
                else:
                    var_multiplier = 1 + np.random.uniform(-0.05, 0.05)
                    spend = int(spend * var_multiplier)
                    clicks = int(clicks * var_multiplier)
                    conversions = int(conversions * var_multiplier)
                    
                mkt_data.append({
                    'date': date.strftime('%Y-%m-%d'),
                    'region': region,
                    'product': product,
                    'campaign': campaign,
                    'spend': spend,
                    'clicks': clicks,
                    'conversions': conversions
                })
                
    pd.DataFrame(mkt_data).to_csv(os.path.join(base_dir, 'marketing.csv'), index=False)
    
    # 3. SUPPORT DATA
    support_data = []
    issue_types = ['delivery_delay', 'product_defect', 'billing_issue', 'feature_request', 'general_inquiry']
    severities = ['critical', 'high', 'medium', 'low']
    
    ticket_counter = 1000
    
    # Generate South spike
    current_dates = pd.date_range(start='2026-08-21', end='2026-08-27')
    south_spike_count = random.randint(12, 15)
    
    south_texts = [
        "Order #XXXXX delayed by 5 days, customer requesting cancellation",
        "Delivery partner reports logistics bottleneck in South region",
        "XPhone Pro shipment stuck at warehouse, estimated 3-day delay",
        "Customer complaint: delivery promised in 2 days, now showing 7 days"
    ]
    
    for _ in range(south_spike_count):
        date = pd.to_datetime(np.random.choice(current_dates))
        support_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'region': 'South',
            'product': 'XPhone Pro',
            'ticket_id': f'TCK-{ticket_counter}',
            'ticket_text': np.random.choice(south_texts),
            'issue_type': 'delivery_delay',
            'severity': np.random.choice(['critical', 'high'])
        })
        ticket_counter += 1
        
    # Generate baseline
    # ~70 baseline tickets
    for _ in range(70):
        date = pd.to_datetime(np.random.choice(dates))
        region = np.random.choice(regions)
        product = np.random.choice(products)
        
        # East + TabMax limit to 1-2 total
        if region == 'East' and product == 'TabMax' and random.random() < 0.9:
            continue
            
        if product == 'NovaWatch' and date < pd.Timestamp('2026-08-16'):
            date = pd.to_datetime(np.random.choice(pd.date_range(start='2026-08-16', end='2026-08-27')))
            
        support_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'region': region,
            'product': product,
            'ticket_id': f'TCK-{ticket_counter}',
            'ticket_text': 'Standard baseline support ticket text',
            'issue_type': np.random.choice(issue_types),
            'severity': np.random.choice(severities)
        })
        ticket_counter += 1
        
    pd.DataFrame(support_data).to_csv(os.path.join(base_dir, 'support.csv'), index=False)
    
    # 4. COMPETITOR DATA
    competitor_data = []
    
    # South scenario
    competitor_data.append({
        'date': '2026-08-20',
        'region': 'South',
        'product': 'XPhone Pro',
        'competitor_name': 'TechRival',
        'competitor_price': 45000,
        'event_type': 'price_reduction',
        'description': 'TechRival reduces XPhone Pro equivalent price from ₹50,000 to ₹45,000 in South region'
    })
    
    # Other events
    for _ in range(12):
        date = pd.to_datetime(np.random.choice(dates))
        region = np.random.choice(regions)
        product = np.random.choice(products)
        
        # East + TabMax limit to 0
        if region == 'East' and product == 'TabMax':
            continue
            
        if product == 'NovaWatch' and date < pd.Timestamp('2026-08-16'):
            date = pd.to_datetime(np.random.choice(pd.date_range(start='2026-08-16', end='2026-08-27')))
            
        competitor_data.append({
            'date': date.strftime('%Y-%m-%d'),
            'region': region,
            'product': product,
            'competitor_name': f'Competitor_{random.randint(1,5)}',
            'competitor_price': int(np.random.uniform(20000, 60000)),
            'event_type': np.random.choice(['price_reduction', 'new_product_launch', 'marketing_campaign']),
            'description': 'Standard competitor event'
        })
        
    pd.DataFrame(competitor_data).to_csv(os.path.join(base_dir, 'competitor.csv'), index=False)

if __name__ == '__main__':
    generate_data()
    print("Data generation completed.")
