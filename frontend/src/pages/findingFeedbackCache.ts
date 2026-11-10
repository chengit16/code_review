/** @description 反馈写入后的同源缓存失效范围；不改变执行、投递或历史问题状态。 */
/** 首页、分页发现、任务与详情均重新读取持久化反馈事实。 */
export const feedbackCacheKeys = ["jobs", "job-neighbors", "job", "review-feedback-summary", "review-issues", "review-issue", "review-effectiveness", "overview", "review-findings", "review-finding"];
