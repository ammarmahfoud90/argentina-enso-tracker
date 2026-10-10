/* Corrected inference is required before the UI highlights a signal.
   Old cached payloads have no q: display their coefficients descriptively. */
function correlationQ(record) {
  return record && Number.isFinite(record.pearson_q) ? record.pearson_q : 1;
}
function frequencyQ(record) {
  return record && Number.isFinite(record.q_binomial) ? record.q_binomial : 1;
}
function frequencySignificant(record) {
  return frequencyQ(record) < 0.05;
}
function correlationStars(record) {
  return correlationQ(record) < 0.05 ? record.pearson_stars || '' : '';
}
