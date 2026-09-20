/*
Title: 3013. Divide an Array Into Subarrays With Minimum Cost II
Solution: https://leetcode.com/problems/divide-an-array-into-subarrays-with-minimum-cost-ii/solutions/7544900/simplest-solution-c-time-on-logdist-spac-yyjb/
Difficulty: Hard
Approach: Sliding Window with Two Sorted Sets
Tags: Array, Sliding Window, Heap (Priority Queue), Greedy
1) First element must be included in the first subarray (fixed constraint).
2) We need to select k-1 elements from a sliding window of size dist+1 to minimize sum.
3) Use two sorted sets: kMinimum (holds k-1 smallest elements) and remaining (holds larger elements).
4) Each element is stored as [value, index] to handle duplicates and maintain order.
5) Build the first window [1...dist+1], adding elements to kMinimum.
6) If kMinimum exceeds k-1 size, move the largest element to remaining set.
7) Slide the window through the array, adding new elements and removing expired ones.
8) When removing expired element, if it's in kMinimum, promote smallest from remaining.
9) Track minimum sum across all windows and return nums[0] + minimum sum.

Time Complexity: O(n * log(dist)) where n = nums.length (each operation on sorted set is O(log size))
Space Complexity: O(dist) for storing elements in the two sorted sets
Tip: The key insight is maintaining two sorted sets to efficiently track the k-1 smallest elements in a sliding window. When an element expires from the window, we can quickly determine if we need to promote an element from remaining to kMinimum.
Similar Problems: 239. Sliding Window Maximum, 480. Sliding Window Median, 3010. Divide an Array Into Subarrays With Minimum Cost I
*/
public class Solution {
    // Custom comparer for sorting by value first, then by index
    private class ValueIndexComparer : IComparer<(int value, int index)> {
        public int Compare((int value, int index) a, (int value, int index) b) {
            if (a.value != b.value)                                 // If values are different, compare by value
                return a.value.CompareTo(b.value);
            return a.index.CompareTo(b.index);                      // If values are same, compare by index to handle duplicates
        }
    }

    public long MinimumCost(int[] nums, int k, int dist) {
        int n = nums.Length;                                        // Get array length

        // SortedSet to maintain k-1 smallest elements in current window
        SortedSet<(int value, int index)> kMinimum = new SortedSet<(int value, int index)>(new ValueIndexComparer());

        // SortedSet to maintain remaining larger elements in current window
        SortedSet<(int value, int index)> remaining = new SortedSet<(int value, int index)>(new ValueIndexComparer());

        long sum = 0;                                               // Sum of k-1 smallest elements in current window
        int i = 1;                                                  // Start from index 1 (index 0 is fixed)

        // Build first window [1 ... dist+1]
        while (i < n && i - dist < 1) {                             // Continue while within first window range
            var cur = (nums[i], i);                                 // Create tuple with current value and index
            kMinimum.Add(cur);                                      // Add current element to kMinimum set
            sum += nums[i];                                         // Add current value to sum

            if (kMinimum.Count > k - 1) {                           // If kMinimum has more than k-1 elements
                var largest = kMinimum.Max;                         // Get the largest element in kMinimum
                kMinimum.Remove(largest);                           // Remove it from kMinimum
                sum -= largest.value;                               // Subtract its value from sum
                remaining.Add(largest);                             // Add it to remaining set
            }
            i++;                                                    // Move to next index
        }

        long result = long.MaxValue;                                // Initialize result with maximum value

        // Sliding window from dist+2 onwards
        while (i < n) {                                             // Continue until end of array
            var cur = (nums[i], i);                                 // Create tuple with current value and index
            kMinimum.Add(cur);                                      // Add current element to kMinimum
            sum += nums[i];                                         // Add current value to sum

            if (kMinimum.Count > k - 1) {                           // If kMinimum has more than k-1 elements
                var largest = kMinimum.Max;                         // Get the largest element in kMinimum
                kMinimum.Remove(largest);                           // Remove it from kMinimum
                sum -= largest.value;                               // Subtract its value from sum
                remaining.Add(largest);                             // Add it to remaining set
            }

            result = Math.Min(result, sum);                         // Update result with minimum sum found so far

            // Remove expired index (element at i - dist)
            int remIdx = i - dist;                                  // Calculate index of element to remove (outside window)
            var toRemove = (nums[remIdx], remIdx);                  // Create tuple for element to remove

            if (kMinimum.Remove(toRemove)) {                        // Try to remove from kMinimum; if successful
                sum -= nums[remIdx];                                // Subtract removed value from sum

                if (remaining.Count > 0) {                          // If remaining set is not empty
                    var promote = remaining.Min;                    // Get smallest element from remaining
                    remaining.Remove(promote);                      // Remove it from remaining
                    kMinimum.Add(promote);                          // Add it to kMinimum (promotion)
                    sum += promote.value;                           // Add its value to sum
                }
            } else {                                                // If element was not in kMinimum
                remaining.Remove(toRemove);                         // Remove it from remaining set instead
            }

            i++;                                                    // Move to next index
        }

        return nums[0] + result;                                    // Return first element plus minimum sum of k-1 elements
    }
}