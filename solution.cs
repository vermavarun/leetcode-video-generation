/*
Title: 3498. Reverse Degree of a String
Solution:
Difficulty: Easy
Approach: Character Position Mapping and Weighted Sum
Tags: String, Math
1) Iterate through each character in the string with its 1-based position.
2) Convert the character to its reverse alphabet position: 'z' has value 1 and 'a' has value 26.
3) Multiply the reverse alphabet position by the character's 1-based position.
4) Add the weighted value to the total reverse degree.
5) Return the total after processing every character.

Time Complexity: O(n) where n = s.length
Space Complexity: O(1) because only the running total is stored
Tip: Subtract the character's zero-based alphabet index from 26 to reverse its alphabet position.
Similar Problems: 3110. Score of a String, 1945. Sum of Digits of String After Convert
*/
public class Solution {
    public int ReverseDegree(string s) {

        int sum = 0;                                      // Store the running reverse degree
        int index = 1;                                    // Track the current 1-based character position

        foreach (char c in s)                            // Iterate through each character
        {
            int alphabetPosition = c - 'a' + 1;          // Convert 'a' to 1, 'b' to 2, ..., 'z' to 26
            int reversePosition = 26 - alphabetPosition + 1; // Reverse the alphabet position: 'a' to 26, 'z' to 1
            sum += reversePosition * index;              // Add the character's weighted reverse position

            index++;                                     // Move to the next 1-based character position
        }

        return sum;                                      // Return the completed reverse degree
    }
}