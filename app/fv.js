/* Fair-value formula used by the dashboard calculator.
 * Same maths as qdii_fve.fair_value.reconstruct.reconstruct_fair_value (tested against it):
 *   FV = NAV(D) * U(t) / U(D) * FX(t) / CFETS_parity(D)
 * Loads as a plain <script> (window.FV) or with require() in Node (module.exports).
 */
(function (root) {
  "use strict";

  function fairValue(nav, underlyingRef, underlyingNow, parityRef, fxNow) {
    if (!(underlyingRef > 0) || !(parityRef > 0)) {
      throw new Error("NAV-date underlying and FX levels must be positive");
    }
    return nav * (underlyingNow / underlyingRef) * (fxNow / parityRef);
  }

  function premiumBp(price, fair) {
    if (!(price > 0) || !(fair > 0)) {
      throw new Error("price and fair value must be positive");
    }
    return Math.log(price / fair) * 1e4;
  }

  /* Split the NAV-to-fair-value move into the underlying and FX parts (log, so they add up). */
  function decompose(underlyingRef, underlyingNow, parityRef, fxNow) {
    const u = Math.log(underlyingNow / underlyingRef) * 1e4;
    const f = Math.log(fxNow / parityRef) * 1e4;
    return { underlyingBp: u, fxBp: f, totalBp: u + f };
  }

  const api = { fairValue: fairValue, premiumBp: premiumBp, decompose: decompose };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    root.FV = api;
  }
})(this);
