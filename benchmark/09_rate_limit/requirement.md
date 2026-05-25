# Rate Limit Decision

Given the number of requests made in the current window so far (count), the per-window limit (limit), and whether the window has just rolled over (rolled), return True if and only if a new request should be allowed: count must be strictly less than limit when the window has NOT just rolled over; on a fresh window, requests are always allowed (the count is implicitly reset).
