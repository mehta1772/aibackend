"""
Machine Learning Service
Revenue prediction and service recommendations
"""

import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any
from collections import defaultdict

class MLService:
    """ML-powered predictions and insights for CRM"""
    
    def __init__(self):
        self.revenue_history = []
        self.service_history = defaultdict(int)
        self.booking_history = []
    
    def load_data(self, bookings: List[Dict[str, Any]]):
        """Load historical booking data"""
        self.booking_history = bookings
        
        # Calculate monthly revenue
        monthly_revenue = defaultdict(float)
        for booking in bookings:
            if booking.get("date"):
                date = booking["date"]
                if isinstance(date, str):
                    date = datetime.fromisoformat(date.replace("Z", "+00:00"))
                month_key = date.strftime("%Y-%m")
                monthly_revenue[month_key] += booking.get("total_amount", 0)
            
            # Count services
            for service in booking.get("services", []):
                self.service_history[service] += 1
        
        self.revenue_history = [
            {"month": k, "revenue": v}
            for k, v in sorted(monthly_revenue.items())
        ]
    
    def predict_next_month_revenue(self) -> Dict[str, Any]:
        """
        Predict next month's revenue using simple moving average
        with trend adjustment
        """
        if len(self.revenue_history) < 3:
            return {
                "predicted_revenue": 0,
                "confidence": 0,
                "trend": "insufficient_data"
            }
        
        revenues = [r["revenue"] for r in self.revenue_history[-12:]]
        
        # Simple moving average (last 3 months)
        sma_3 = np.mean(revenues[-3:])
        
        # Trend calculation
        if len(revenues) >= 6:
            recent_avg = np.mean(revenues[-3:])
            older_avg = np.mean(revenues[-6:-3])
            trend_factor = recent_avg / older_avg if older_avg > 0 else 1
        else:
            trend_factor = 1
        
        # Seasonal adjustment (basic)
        seasonal_factor = 1.0
        current_month = datetime.now().month
        
        # Q4 boost (October-December typically higher)
        if current_month in [10, 11, 12]:
            seasonal_factor = 1.1
        # Q1 slight dip (January-March)
        elif current_month in [1, 2, 3]:
            seasonal_factor = 0.95
        
        # Final prediction
        predicted = sma_3 * trend_factor * seasonal_factor
        
        # Confidence based on data consistency
        std_dev = np.std(revenues)
        mean_rev = np.mean(revenues)
        cv = std_dev / mean_rev if mean_rev > 0 else 1  # Coefficient of variation
        confidence = max(0.3, min(0.95, 1 - cv))  # Higher CV = lower confidence
        
        # Determine trend direction
        if trend_factor > 1.05:
            trend = "up"
        elif trend_factor < 0.95:
            trend = "down"
        else:
            trend = "stable"
        
        return {
            "predicted_revenue": round(predicted, 2),
            "confidence": round(confidence, 2),
            "trend": trend,
            "trend_factor": round(trend_factor, 2),
            "seasonal_factor": seasonal_factor
        }
    
    def recommend_services(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """
        Recommend best-performing services based on:
        - Booking frequency
        - Revenue contribution
        - Growth trend
        """
        if not self.service_history:
            return []
        
        # Calculate service metrics
        service_metrics = []
        total_bookings = sum(self.service_history.values())
        
        # Calculate revenue per service
        service_revenue = defaultdict(float)
        for booking in self.booking_history:
            services = booking.get("services", [])
            amount_per_service = booking.get("total_amount", 0) / len(services) if services else 0
            for service in services:
                service_revenue[service] += amount_per_service
        
        total_revenue = sum(service_revenue.values())
        
        for service, count in self.service_history.items():
            frequency_score = count / total_bookings if total_bookings > 0 else 0
            revenue_score = service_revenue[service] / total_revenue if total_revenue > 0 else 0
            
            # Combined score (weighted)
            combined_score = (frequency_score * 0.4) + (revenue_score * 0.6)
            
            service_metrics.append({
                "service": service,
                "booking_count": count,
                "revenue": round(service_revenue[service], 2),
                "frequency_score": round(frequency_score, 3),
                "revenue_score": round(revenue_score, 3),
                "combined_score": round(combined_score, 3)
            })
        
        # Sort by combined score
        service_metrics.sort(key=lambda x: x["combined_score"], reverse=True)
        
        # Generate recommendations
        recommendations = []
        for i, svc in enumerate(service_metrics[:top_n]):
            if svc["combined_score"] > 0.15:
                reason = f"Top performer with {svc['booking_count']} bookings and ₹{svc['revenue']:,.0f} revenue"
            elif svc["revenue_score"] > svc["frequency_score"]:
                reason = "High-value service with strong revenue per booking"
            else:
                reason = "Popular service with consistent demand"
            
            recommendations.append({
                "service": svc["service"],
                "score": round(svc["combined_score"] * 100, 1),
                "reason": reason,
                "metrics": {
                    "bookings": svc["booking_count"],
                    "revenue": svc["revenue"]
                }
            })
        
        return recommendations
    
    def get_ad_strategy(self) -> List[str]:
        """Generate ad strategy recommendations based on data analysis"""
        recommendations = []
        
        prediction = self.predict_next_month_revenue()
        top_services = self.recommend_services(3)
        
        # Trend-based recommendations
        if prediction["trend"] == "up":
            recommendations.append(
                "📈 Revenue is trending up! Consider increasing ad spend to capitalize on momentum."
            )
        elif prediction["trend"] == "down":
            recommendations.append(
                "📉 Revenue trend is declining. Focus ads on your best-performing services to stabilize."
            )
        else:
            recommendations.append(
                "📊 Revenue is stable. A/B test new ad creatives to find growth opportunities."
            )
        
        # Service-specific recommendations
        if top_services:
            top_service = top_services[0]["service"]
            recommendations.append(
                f"🎯 Double down on '{top_service}' - it's your strongest performer. "
                f"Allocate 40% of ad budget here."
            )
            
            if len(top_services) >= 2:
                second_service = top_services[1]["service"]
                recommendations.append(
                    f"🔄 Cross-sell '{second_service}' to existing customers. "
                    f"Create bundle offers combining top services."
                )
        
        # Seasonal recommendations
        current_month = datetime.now().month
        if current_month in [10, 11, 12]:
            recommendations.append(
                "🎄 Q4 is typically strong. Increase ad frequency for year-end deals."
            )
        elif current_month in [1, 2, 3]:
            recommendations.append(
                "🌱 Q1 can be slow. Focus on retention campaigns and referral programs."
            )
        elif current_month in [4, 5, 6]:
            recommendations.append(
                "☀️ Q2 is prime time for new customer acquisition. Expand targeting."
            )
        
        # Lead generation recommendations
        recommendations.append(
            "💡 Use lookalike audiences based on your best customers to improve lead quality."
        )
        recommendations.append(
            "📧 Implement retargeting campaigns for website visitors who didn't convert."
        )
        
        return recommendations
    
    def get_customer_insights(self) -> Dict[str, Any]:
        """Analyze customer patterns"""
        if not self.booking_history:
            return {"message": "Insufficient data"}
        
        # Average booking value
        total_revenue = sum(b.get("total_amount", 0) for b in self.booking_history)
        avg_booking_value = total_revenue / len(self.booking_history) if self.booking_history else 0
        
        # Most common state/region
        state_count = defaultdict(int)
        for booking in self.booking_history:
            state = booking.get("state", "Unknown")
            if state:
                state_count[state] += 1
        
        top_states = sorted(state_count.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Payment term preferences
        term_usage = {"term_1": 0, "term_2": 0, "term_3": 0}
        for booking in self.booking_history:
            if booking.get("term_1"):
                term_usage["term_1"] += 1
            if booking.get("term_2"):
                term_usage["term_2"] += 1
            if booking.get("term_3"):
                term_usage["term_3"] += 1
        
        return {
            "total_customers": len(self.booking_history),
            "average_booking_value": round(avg_booking_value, 2),
            "top_states": [{"state": s, "count": c} for s, c in top_states],
            "payment_terms_usage": term_usage,
            "total_revenue": round(total_revenue, 2)
        }


# Singleton instance
ml_service = MLService()
