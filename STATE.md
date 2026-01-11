# STATE.md - Ralph Mode Knowledge Base

## Invariants
1. **Engine Integrity**: The core engine must be deterministic. Same inputs -> Same outputs.
2. **Strategy Interface**: Strategies must implement `on_candle(candle, state)` and return a list of `Order` objects (or `OrderRequest`).
3. **No Lookahead**: Strategies must only access data from the current candle or prior.

## Assumptions
1. **Time**: Time is represented in epoch seconds.
2. **Execution**: Orders returned by `on_candle` are processed at the *close* of the current candle (effectively Open of next? Or immediate Market execution? - *To be clarified in implementation*). Current assumption: Market orders execute at Close price of current candle (or Open of next). Limit/Stop orders are added to pending.

## Failure Modes
*None yet defined.*
