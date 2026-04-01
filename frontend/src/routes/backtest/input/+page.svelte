<script lang="ts">
  // Optional: handle form success/error via use:enhance
  import { enhance } from '$app/forms';

  const strategyPlaceholder =
    "export function onBar(bar) {\n" +
    "  if (bar.close > sma(20)) buy();\n" +
    "  else sell();\n" +
    "}";
</script>

<h1>Backtest Strategy</h1>

<form method="POST" use:enhance>
  <label>
    Strategy Code (TypeScript-like)
	    <textarea 
	      name="strategyCode" 
	      rows="12"
	      placeholder={strategyPlaceholder}
	    ></textarea>
	  </label>

  <label>
    Initial Capital ($)
    <input type="number" name="initialCapital" value="10000" min="1" />
  </label>

  <button type="submit">🚀 Run Backtest</button>
</form>
