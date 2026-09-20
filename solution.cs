/*
Title: 1622. Fancy Sequence
Solution: https://leetcode.com/problems/fancy-sequence/solutions/7650344/simplest-solution-c-time-olog-n-space-on-y3cr/
Difficulty: Hard
Approach: Modular Arithmetic with Lazy Propagation - store transformation coefficients instead of updating all elements
Tags: Array, Math, Modular Arithmetic
1) Represent each element as a transformed value: real_value = a * stored_value + b
2) Instead of updating all elements, only update the global transformation coefficients a and b
3) For append(val), calculate the normalized stored value using modular inverse: stored = (val - b) * a^(-1) % MOD
4) For addAll(inc), only increment b since value = a*x + (b + inc)
5) For multAll(m), multiply both a and b since value = m*(a*x + b) = (a*m)*x + (b*m)
6) For getIndex(idx), apply the transformation: return (a * stored + b) % MOD
7) Use Fermat's Little Theorem for modular inverse: a^(-1) = a^(MOD-2) % MOD

Time Complexity: O(log n) per operation due to modular exponentiation
Space Complexity: O(n) for storing the normalized values
Tip: The key insight is lazy evaluation - instead of updating millions of elements for addAll/multAll operations, maintain transformation coefficients (a,b) and apply them only when retrieving values. This trades O(n) updates for O(1) coefficient updates and O(log n) modular exponentiation during append/getIndex.
Similar Problems: 1157. Online Majority Element In Subarray, 1618. Maximum Font to Fit a Sentence in a Screen
*/
using System;
using System.Collections.Generic;

public class Fancy
{
    /*
    Key Idea - Lazy Propagation with Transformation Coefficients:
    Instead of updating every element when addAll or multAll is called,
    we store elements in a transformed form using two coefficients.

    Every real value in the sequence is represented as:
        real_value = a * stored_value + b

    where:
        a -> multiplication factor (initially 1)
        b -> addition factor (initially 0)

    This allows O(1) addAll and multAll operations while maintaining accuracy.
    We only calculate the real value when needed (during getIndex).
    */

    private const long MOD = 1000000007;                          // Prime modulus for all arithmetic operations

    // Stored normalized values - each value is stored in their base form
    private List<long> vals = new List<long>();

    // Global transformation coefficients - represent the current transformation state
    private long a = 1;                                           // Multiplication factor
    private long b = 0;                                           // Addition factor

    /*
    append(val) - Add a value to the sequence in its normalized form

    We need to store the value in normalized form such that:
        val = a * stored + b

    Solving for stored:
        stored = (val - b) / a

    Since division under modulo is not allowed, we use modular inverse:
        stored = (val - b) * a^(MOD-2) % MOD (by Fermat's Little Theorem)

    Example:
    Suppose a = 2, b = 3, and we append(11)
    11 = 2*x + 3
    x = (11 - 3) / 2 = 4
    So we store normalized value 4, and when retrieved: 2*4 + 3 = 11
    */

    public void Append(int val)
    {
        // Subtract current addition factor from the value to normalize
        long x = (val - b + MOD) % MOD;

        // Calculate modular inverse of 'a' to perform division under modulo
        // normalized = x / a = x * a^(MOD-2) % MOD
        long normalized = (x * ModPow(a, MOD - 2)) % MOD;

        // Store the normalized value
        vals.Add(normalized);
    }

    /*
    addAll(inc) - Add a value to all elements (only update the addition factor)

    Current transformation formula:
        value = a * x + b

    After adding inc to all elements:
        value = a * x + (b + inc)

    Notice that only the addition factor b changes - no need to update stored values!
    This is the power of lazy propagation.
    */

    public void AddAll(int inc)
    {
        // Update the global addition factor by the increment
        b = (b + inc) % MOD;
    }

    /*
    multAll(m) - Multiply all elements by a factor (update both coefficients)

    Current transformation formula:
        value = a * x + b

    After multiplying all elements by m:
        value = m * (a * x + b)
              = (a * m) * x + (b * m)

    Both multiplication factor a and addition factor b must be updated.
    */

    public void MultAll(int m)
    {
        // Both coefficients are multiplied by the factor m
        a = (a * m) % MOD;                                        // Update multiplication factor
        b = (b * m) % MOD;                                        // Update addition factor
    }

    /*
    getIndex(idx) - Retrieve the actual value at index by applying transformation

    Apply the transformation formula to the stored normalized value:
        Real value = a * stored + b

    Example:
        stored = 4, a = 2, b = 3
        Real value = 2*4 + 3 = 11

    Return -1 if the index is out of bounds.
    */

    public int GetIndex(int idx)
    {
        // Validate index bounds
        if (idx >= vals.Count)
            return -1;                                            // Index out of range

        // Apply transformation to retrieve the actual value
        return (int)((a * vals[idx] + b) % MOD);
    }

    /*
    ModPow(x, n) - Fast modular exponentiation using binary exponentiation
    Used for calculating modular inverse via Fermat's Little Theorem

    Fermat's Little Theorem (p is prime):
        a^(p-1) ≡ 1 (mod p)
        a^(p-2) ≡ a^(-1) (mod p)  [modular inverse]

    Since MOD = 1000000007 is prime, we can use this to find a^(-1) = a^(MOD-2) % MOD
    This is needed for division operations under modulo arithmetic.

    Binary exponentiation reduces time complexity from O(n) to O(log n).
    */

    private long ModPow(long x, long n)
    {
        // Base case: x^0 = 1
        if (n == 0)
            return 1;

        // Calculate x^(n/2) recursively (divide exponent by 2)
        long half = ModPow(x, n / 2);

        // Square the result: (x^(n/2))^2 = x^n (if n is even)
        long result = (half * half) % MOD;

        // If n is odd, multiply by x one more time: x^(n+1) = x^n * x
        if (n % 2 == 1)
            result = (result * x) % MOD;

        return result;
    }
}