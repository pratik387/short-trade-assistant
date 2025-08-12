# services/intraday/planner.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, List
import openai
import os
import json
from openai import OpenAI

openai.api_key = os.getenv("OPENAI_API_KEY")

@dataclass
class Plan:
    entry_note: str
    entry_zone: Tuple[float, float]
    stop: float
    targets: List[float]
    confidence: float
    rr_first: float  # R:R to first target

def make_plan(symbol: str, indicators: dict, context: dict) -> dict:
    """
    Use ChatGPT to generate an intraday trade plan given a stock's context.

    Args:
      symbol: Stock symbol (e.g., RELIABLE.NS)
      indicators: Dict of RSI, ADX, volume_ratio, etc.
      context: Dict containing latest price, ORB high/low, VWAP, previous levels

    Returns:
      Dict with plan fields (entry_note, entry_zone, stop, targets, confidence, rr_first)
    """
    prompt = f"""
You are a professional trading assistant. Based on the following data, suggest an intraday trade plan for {symbol}.

Data:
- Current Price: {context.get('price')}
- VWAP: {context.get('vwap')}
- ORB High/Low: {context.get('orb_high')} / {context.get('orb_low')}
- Prev High/Low: {context.get('prev_high')} / {context.get('prev_low')}
- RSI: {indicators.get('rsi')}
- ADX: {indicators.get('adx')}
- Volume Ratio: {indicators.get('volume_ratio')}

{ 'Note: It is early in the trading session (before 10am). You may only have 3–5 candles. Indicators like RSI and ADX might not be reliable or even available yet. If momentum is strong, still suggest a breakout or pullback plan even with limited data.' if context.get('early') else '' }

Define:
- Entry zone (breakout or pullback)
- Stop loss below key level
- 1–2 target levels
- A short reason (e.g., momentum breakout above VWAP)

Respond in JSON format like:
{{
  "entry_note": "...",
  "entry_zone": [entry_lo, entry_hi],
  "stop": ..., 
  "targets": [target1, target2],
  "confidence": 0.xx,
  "rr_first": 0.xx
}}
"""

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a trading assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            response_format={"type": "json_object"},
        )

        text = response.choices[0].message.content        
        return json.loads(text)

    except Exception as e:
        return {
            "entry_note": f"LLM failed: {e}",
            "entry_zone": (0, 0),
            "stop": 0,
            "targets": [],
            "confidence": 0,
            "rr_first": 0
        }

