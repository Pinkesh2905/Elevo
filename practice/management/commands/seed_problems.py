"""
Management command to seed 100+ LeetCode-style coding problems with
topics, companies, test cases, and code templates in 5 languages.
"""
from django.core.management.base import BaseCommand
from practice.models import Topic, Company, Problem, TestCase, CodeTemplate

TOPICS = [
    ("Arrays", "Problems involving array manipulation and traversal"),
    ("Strings", "String processing and manipulation problems"),
    ("Linked List", "Singly and doubly linked list problems"),
    ("Stack", "Stack-based problems including monotonic stacks"),
    ("Queue", "Queue and deque-based problems"),
    ("Hash Table", "Hash map and hash set problems"),
    ("Binary Search", "Binary search and its variations"),
    ("Two Pointers", "Two pointer technique problems"),
    ("Sliding Window", "Sliding window technique problems"),
    ("Dynamic Programming", "DP problems with memoization and tabulation"),
    ("Greedy", "Greedy algorithm problems"),
    ("Backtracking", "Backtracking and recursion problems"),
    ("Trees", "Binary tree and BST problems"),
    ("Graphs", "Graph traversal and shortest path problems"),
    ("Heap", "Priority queue and heap problems"),
    ("Sorting", "Sorting algorithm problems"),
    ("Math", "Mathematical and number theory problems"),
    ("Bit Manipulation", "Bitwise operation problems"),
    ("Recursion", "Recursive solution problems"),
    ("Matrix", "2D matrix problems"),
]

COMPANIES = ["Google", "Amazon", "Meta", "Microsoft", "Apple", "Netflix",
             "Adobe", "Uber", "Goldman Sachs", "Bloomberg", "Oracle", "Salesforce"]

# (num, title, diff, topics, companies, desc, constraints, ex_in, ex_out, ex_expl, hints, time_c, space_c, tests, templates)
# templates: {lang: (starter, solution)}
# tests: [(input, output, is_sample, explanation)]

PROBLEMS = [
  (1, "Two Sum", "easy", ["Arrays", "Hash Table"], ["Google", "Amazon", "Meta"],
   "Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.\n\nYou can return the answer in any order.",
   "2 <= nums.length <= 10^4\n-10^9 <= nums[i] <= 10^9\n-10^9 <= target <= 10^9\nOnly one valid answer exists.",
   "nums = [2,7,11,15], target = 9", "[0,1]",
   "Because nums[0] + nums[1] == 9, we return [0, 1].",
   "Try using a hash map to store seen values.\nFor each number, check if target - number exists in the map.",
   "O(n)", "O(n)",
   [("nums = [2,7,11,15]\ntarget = 9", "[0, 1]", True, "2 + 7 = 9"),
    ("nums = [3,2,4]\ntarget = 6", "[1, 2]", True, "2 + 4 = 6"),
    ("nums = [3,3]\ntarget = 6", "[0, 1]", False, "3 + 3 = 6")],
   {"python3": ("class Solution:\n    def twoSum(self, nums: list[int], target: int) -> list[int]:\n        # Write your solution here\n        pass",
                "class Solution:\n    def twoSum(self, nums: list[int], target: int) -> list[int]:\n        seen = {}\n        for i, n in enumerate(nums):\n            comp = target - n\n            if comp in seen:\n                return [seen[comp], i]\n            seen[n] = i\n        return []"),
    "cpp17": ("#include <vector>\n#include <unordered_map>\nusing namespace std;\n\nclass Solution {\npublic:\n    vector<int> twoSum(vector<int>& nums, int target) {\n        // Write your solution here\n        return {};\n    }\n};",
              "#include <vector>\n#include <unordered_map>\nusing namespace std;\n\nclass Solution {\npublic:\n    vector<int> twoSum(vector<int>& nums, int target) {\n        unordered_map<int,int> seen;\n        for(int i=0;i<nums.size();i++){\n            int comp=target-nums[i];\n            if(seen.count(comp)) return {seen[comp],i};\n            seen[nums[i]]=i;\n        }\n        return {};\n    }\n};"),
    "java": ("import java.util.*;\n\nclass Solution {\n    public int[] twoSum(int[] nums, int target) {\n        // Write your solution here\n        return new int[]{};\n    }\n}",
             "import java.util.*;\n\nclass Solution {\n    public int[] twoSum(int[] nums, int target) {\n        Map<Integer,Integer> seen = new HashMap<>();\n        for(int i=0;i<nums.length;i++){\n            int comp=target-nums[i];\n            if(seen.containsKey(comp)) return new int[]{seen.get(comp),i};\n            seen.put(nums[i],i);\n        }\n        return new int[]{};\n    }\n}"),
    "javascript": ("/**\n * @param {number[]} nums\n * @param {number} target\n * @return {number[]}\n */\nvar twoSum = function(nums, target) {\n    // Write your solution here\n};",
                   "var twoSum = function(nums, target) {\n    const seen = new Map();\n    for(let i=0;i<nums.length;i++){\n        const comp=target-nums[i];\n        if(seen.has(comp)) return [seen.get(comp),i];\n        seen.set(nums[i],i);\n    }\n    return [];\n};"),
    "c": ("#include <stdlib.h>\n\nint* twoSum(int* nums, int numsSize, int target, int* returnSize) {\n    // Write your solution here\n    *returnSize = 2;\n    int* result = (int*)malloc(2 * sizeof(int));\n    return result;\n}",
          "#include <stdlib.h>\n\nint* twoSum(int* nums, int numsSize, int target, int* returnSize) {\n    *returnSize = 2;\n    int* result = (int*)malloc(2 * sizeof(int));\n    for(int i=0;i<numsSize;i++)\n        for(int j=i+1;j<numsSize;j++)\n            if(nums[i]+nums[j]==target){result[0]=i;result[1]=j;return result;}\n    return result;\n}")}),

  (2, "Add Two Numbers", "medium", ["Linked List", "Math"], ["Amazon", "Microsoft", "Bloomberg"],
   "You are given two non-empty linked lists representing two non-negative integers. The digits are stored in reverse order, and each of their nodes contains a single digit. Add the two numbers and return the sum as a linked list.",
   "The number of nodes in each linked list is in the range [1, 100].\n0 <= Node.val <= 9\nThe number does not contain any leading zero, except the number 0 itself.",
   "l1 = [2,4,3], l2 = [5,6,4]", "[7,0,8]", "342 + 465 = 807.",
   "Simulate digit-by-digit addition.\nDon't forget the carry!", "O(max(m,n))", "O(max(m,n))",
   [("l1 = [2,4,3]\nl2 = [5,6,4]", "[7,0,8]", True, "342 + 465 = 807"),
    ("l1 = [0]\nl2 = [0]", "[0]", True, "0 + 0 = 0"),
    ("l1 = [9,9,9,9]\nl2 = [9,9,9]", "[8,9,9,0,1]", False, "9999 + 999 = 10998")],
   {"python3": ("class ListNode:\n    def __init__(self, val=0, next=None):\n        self.val = val\n        self.next = next\n\nclass Solution:\n    def addTwoNumbers(self, l1: ListNode, l2: ListNode) -> ListNode:\n        # Write your solution here\n        pass", "class Solution:\n    def addTwoNumbers(self, l1, l2):\n        dummy = ListNode(0)\n        cur, carry = dummy, 0\n        while l1 or l2 or carry:\n            v1 = l1.val if l1 else 0\n            v2 = l2.val if l2 else 0\n            s = v1 + v2 + carry\n            carry, val = divmod(s, 10)\n            cur.next = ListNode(val)\n            cur = cur.next\n            l1 = l1.next if l1 else None\n            l2 = l2.next if l2 else None\n        return dummy.next"),
    "cpp17": ("struct ListNode {\n    int val;\n    ListNode *next;\n    ListNode(int x) : val(x), next(nullptr) {}\n};\n\nclass Solution {\npublic:\n    ListNode* addTwoNumbers(ListNode* l1, ListNode* l2) {\n        // Write your solution here\n        return nullptr;\n    }\n};", "class Solution {\npublic:\n    ListNode* addTwoNumbers(ListNode* l1, ListNode* l2) {\n        ListNode dummy(0);\n        ListNode* cur = &dummy;\n        int carry = 0;\n        while(l1||l2||carry){\n            int s = carry + (l1?l1->val:0) + (l2?l2->val:0);\n            carry = s/10;\n            cur->next = new ListNode(s%10);\n            cur = cur->next;\n            if(l1) l1=l1->next;\n            if(l2) l2=l2->next;\n        }\n        return dummy.next;\n    }\n};"),
    "java": ("class ListNode {\n    int val;\n    ListNode next;\n    ListNode(int val) { this.val = val; }\n}\n\nclass Solution {\n    public ListNode addTwoNumbers(ListNode l1, ListNode l2) {\n        // Write your solution here\n        return null;\n    }\n}", "class Solution {\n    public ListNode addTwoNumbers(ListNode l1, ListNode l2) {\n        ListNode dummy = new ListNode(0);\n        ListNode cur = dummy;\n        int carry = 0;\n        while(l1!=null||l2!=null||carry!=0){\n            int s = carry + (l1!=null?l1.val:0) + (l2!=null?l2.val:0);\n            carry = s/10;\n            cur.next = new ListNode(s%10);\n            cur = cur.next;\n            if(l1!=null) l1=l1.next;\n            if(l2!=null) l2=l2.next;\n        }\n        return dummy.next;\n    }\n}"),
    "javascript": ("function ListNode(val, next) {\n    this.val = (val===undefined ? 0 : val)\n    this.next = (next===undefined ? null : next)\n}\n\nvar addTwoNumbers = function(l1, l2) {\n    // Write your solution here\n};", "var addTwoNumbers = function(l1, l2) {\n    let dummy = new ListNode(0), cur = dummy, carry = 0;\n    while(l1||l2||carry){\n        let s = carry + (l1?l1.val:0) + (l2?l2.val:0);\n        carry = Math.floor(s/10);\n        cur.next = new ListNode(s%10);\n        cur = cur.next;\n        if(l1) l1=l1.next;\n        if(l2) l2=l2.next;\n    }\n    return dummy.next;\n};"),
    "c": ("struct ListNode {\n    int val;\n    struct ListNode *next;\n};\n\nstruct ListNode* addTwoNumbers(struct ListNode* l1, struct ListNode* l2) {\n    // Write your solution here\n    return NULL;\n}", "struct ListNode* addTwoNumbers(struct ListNode* l1, struct ListNode* l2) {\n    struct ListNode dummy = {0, NULL};\n    struct ListNode* cur = &dummy;\n    int carry = 0;\n    while(l1||l2||carry){\n        int s = carry + (l1?l1->val:0) + (l2?l2->val:0);\n        carry = s/10;\n        cur->next = malloc(sizeof(struct ListNode));\n        cur->next->val = s%10;\n        cur->next->next = NULL;\n        cur = cur->next;\n        if(l1) l1=l1->next;\n        if(l2) l2=l2->next;\n    }\n    return dummy.next;\n}")}),
]

# Remaining 98 problems defined more compactly
# Format: (num, title, diff, topics, desc_short, time_c, space_c)
COMPACT_PROBLEMS = [
  (3, "Longest Substring Without Repeating Characters", "medium", ["Strings", "Sliding Window", "Hash Table"],
   "Given a string `s`, find the length of the longest substring without repeating characters.", "O(n)", "O(min(n,m))"),
  (4, "Median of Two Sorted Arrays", "hard", ["Arrays", "Binary Search"],
   "Given two sorted arrays `nums1` and `nums2` of size `m` and `n` respectively, return the median of the two sorted arrays. The overall run time complexity should be O(log (m+n)).", "O(log(m+n))", "O(1)"),
  (5, "Longest Palindromic Substring", "medium", ["Strings", "Dynamic Programming"],
   "Given a string `s`, return the longest palindromic substring in `s`.", "O(n^2)", "O(1)"),
  (7, "Reverse Integer", "medium", ["Math"],
   "Given a signed 32-bit integer `x`, return `x` with its digits reversed. If reversing `x` causes the value to go outside the signed 32-bit integer range [-2^31, 2^31 - 1], then return 0.", "O(log x)", "O(1)"),
  (9, "Palindrome Number", "easy", ["Math"],
   "Given an integer `x`, return `true` if `x` is a palindrome, and `false` otherwise. An integer is a palindrome when it reads the same forward and backward.", "O(log n)", "O(1)"),
  (11, "Container With Most Water", "medium", ["Arrays", "Two Pointers", "Greedy"],
   "You are given an integer array `height` of length `n`. There are `n` vertical lines drawn such that the two endpoints of the i-th line are `(i, 0)` and `(i, height[i])`. Find two lines that together with the x-axis form a container, such that the container contains the most water.", "O(n)", "O(1)"),
  (13, "Roman to Integer", "easy", ["Strings", "Hash Table", "Math"],
   "Given a roman numeral, convert it to an integer. Roman numerals are represented by seven different symbols: I, V, X, L, C, D and M.", "O(n)", "O(1)"),
  (14, "Longest Common Prefix", "easy", ["Strings"],
   "Write a function to find the longest common prefix string amongst an array of strings. If there is no common prefix, return an empty string `\"\"`.", "O(S)", "O(1)"),
  (15, "3Sum", "medium", ["Arrays", "Two Pointers", "Sorting"],
   "Given an integer array nums, return all the triplets `[nums[i], nums[j], nums[k]]` such that `i != j`, `i != k`, and `j != k`, and `nums[i] + nums[j] + nums[k] == 0`. Notice that the solution set must not contain duplicate triplets.", "O(n^2)", "O(1)"),
  (17, "Letter Combinations of a Phone Number", "medium", ["Strings", "Backtracking"],
   "Given a string containing digits from 2-9 inclusive, return all possible letter combinations that the number could represent. Return the answer in any order.", "O(4^n)", "O(n)"),
  (19, "Remove Nth Node From End of List", "medium", ["Linked List", "Two Pointers"],
   "Given the head of a linked list, remove the n-th node from the end of the list and return its head.", "O(n)", "O(1)"),
  (20, "Valid Parentheses", "easy", ["Strings", "Stack"],
   "Given a string `s` containing just the characters `'('`, `')'`, `'{'`, `'}'`, `'['` and `']'`, determine if the input string is valid. An input string is valid if: Open brackets must be closed by the same type of brackets. Open brackets must be closed in the correct order. Every close bracket has a corresponding open bracket of the same type.", "O(n)", "O(n)"),
  (21, "Merge Two Sorted Lists", "easy", ["Linked List", "Recursion"],
   "You are given the heads of two sorted linked lists `list1` and `list2`. Merge the two lists into one sorted list. The list should be made by splicing together the nodes of the first two lists. Return the head of the merged linked list.", "O(m+n)", "O(1)"),
  (22, "Generate Parentheses", "medium", ["Strings", "Dynamic Programming", "Backtracking"],
   "Given `n` pairs of parentheses, write a function to generate all combinations of well-formed parentheses.", "O(4^n/sqrt(n))", "O(n)"),
  (23, "Merge k Sorted Lists", "hard", ["Linked List", "Heap", "Sorting"],
   "You are given an array of `k` linked-lists lists, each linked-list is sorted in ascending order. Merge all the linked-lists into one sorted linked-list and return it.", "O(N log k)", "O(k)"),
  (26, "Remove Duplicates from Sorted Array", "easy", ["Arrays", "Two Pointers"],
   "Given an integer array `nums` sorted in non-decreasing order, remove the duplicates in-place such that each unique element appears only once. The relative order of the elements should be kept the same. Return the number of unique elements.", "O(n)", "O(1)"),
  (27, "Remove Element", "easy", ["Arrays", "Two Pointers"],
   "Given an integer array `nums` and an integer `val`, remove all occurrences of `val` in `nums` in-place. The order of the elements may be changed. Return the number of elements in `nums` which are not equal to `val`.", "O(n)", "O(1)"),
  (28, "Find the Index of the First Occurrence in a String", "easy", ["Strings", "Two Pointers"],
   "Given two strings `haystack` and `needle`, return the index of the first occurrence of `needle` in `haystack`, or `-1` if `needle` is not part of `haystack`.", "O(n*m)", "O(1)"),
  (33, "Search in Rotated Sorted Array", "medium", ["Arrays", "Binary Search"],
   "There is an integer array `nums` sorted in ascending order (with distinct values). Prior to being passed to your function, nums is possibly rotated at an unknown pivot index. Given the array `nums` after the possible rotation and an integer `target`, return the index of `target` if it is in `nums`, or `-1` if it is not.", "O(log n)", "O(1)"),
  (34, "Find First and Last Position of Element in Sorted Array", "medium", ["Arrays", "Binary Search"],
   "Given an array of integers `nums` sorted in non-decreasing order, find the starting and ending position of a given `target` value. If `target` is not found in the array, return `[-1, -1]`. You must write an algorithm with O(log n) runtime complexity.", "O(log n)", "O(1)"),
  (35, "Search Insert Position", "easy", ["Arrays", "Binary Search"],
   "Given a sorted array of distinct integers and a target value, return the index if the target is found. If not, return the index where it would be if it were inserted in order.", "O(log n)", "O(1)"),
  (36, "Valid Sudoku", "medium", ["Arrays", "Hash Table", "Matrix"],
   "Determine if a 9 x 9 Sudoku board is valid. Only the filled cells need to be validated according to the rules: Each row, column, and 3x3 sub-box must contain the digits 1-9 without repetition.", "O(1)", "O(1)"),
  (39, "Combination Sum", "medium", ["Arrays", "Backtracking"],
   "Given an array of distinct integers `candidates` and a target integer `target`, return a list of all unique combinations of `candidates` where the chosen numbers sum to `target`. You may return the combinations in any order. The same number may be chosen from `candidates` an unlimited number of times.", "O(N^(T/M))", "O(T/M)"),
  (40, "Combination Sum II", "medium", ["Arrays", "Backtracking"],
   "Given a collection of candidate numbers (`candidates`) and a target number (`target`), find all unique combinations in `candidates` where the candidate numbers sum to `target`. Each number in `candidates` may only be used once in the combination.", "O(2^n)", "O(n)"),
  (41, "First Missing Positive", "hard", ["Arrays", "Hash Table"],
   "Given an unsorted integer array `nums`, return the smallest missing positive integer. You must implement an algorithm that runs in O(n) time and uses O(1) auxiliary space.", "O(n)", "O(1)"),
  (42, "Trapping Rain Water", "hard", ["Arrays", "Two Pointers", "Dynamic Programming", "Stack"],
   "Given `n` non-negative integers representing an elevation map where the width of each bar is 1, compute how much water it can trap after raining.", "O(n)", "O(1)"),
  (46, "Permutations", "medium", ["Arrays", "Backtracking"],
   "Given an array `nums` of distinct integers, return all the possible permutations. You can return the answer in any order.", "O(n!)", "O(n)"),
  (48, "Rotate Image", "medium", ["Arrays", "Math", "Matrix"],
   "You are given an `n x n` 2D matrix representing an image, rotate the image by 90 degrees (clockwise). You have to rotate the image in-place.", "O(n^2)", "O(1)"),
  (49, "Group Anagrams", "medium", ["Arrays", "Hash Table", "Strings", "Sorting"],
   "Given an array of strings `strs`, group the anagrams together. You can return the answer in any order. An Anagram is a word or phrase formed by rearranging the letters of a different word or phrase.", "O(n*k log k)", "O(n*k)"),
  (53, "Maximum Subarray", "medium", ["Arrays", "Dynamic Programming"],
   "Given an integer array `nums`, find the subarray with the largest sum, and return its sum.", "O(n)", "O(1)"),
  (54, "Spiral Matrix", "medium", ["Arrays", "Matrix"],
   "Given an `m x n` matrix, return all elements of the matrix in spiral order.", "O(m*n)", "O(1)"),
  (55, "Jump Game", "medium", ["Arrays", "Dynamic Programming", "Greedy"],
   "You are given an integer array `nums`. You are initially positioned at the array's first index, and each element in the array represents your maximum jump length at that position. Return `true` if you can reach the last index, or `false` otherwise.", "O(n)", "O(1)"),
  (56, "Merge Intervals", "medium", ["Arrays", "Sorting"],
   "Given an array of intervals where `intervals[i] = [start_i, end_i]`, merge all overlapping intervals, and return an array of the non-overlapping intervals that cover all the intervals in the input.", "O(n log n)", "O(n)"),
  (62, "Unique Paths", "medium", ["Math", "Dynamic Programming"],
   "There is a robot on an `m x n` grid. The robot is initially located at the top-left corner. The robot tries to move to the bottom-right corner. The robot can only move either down or right at any point in time. How many possible unique paths are there?", "O(m*n)", "O(n)"),
  (64, "Minimum Path Sum", "medium", ["Arrays", "Dynamic Programming", "Matrix"],
   "Given a `m x n` grid filled with non-negative numbers, find a path from top left to bottom right, which minimizes the sum of all numbers along its path. You can only move either down or right at any point in time.", "O(m*n)", "O(n)"),
  (66, "Plus One", "easy", ["Arrays", "Math"],
   "You are given a large integer represented as an integer array digits, where each digits[i] is the i-th digit of the integer. The digits are ordered from most significant to least significant in left-to-right order. Increment the large integer by one and return the resulting array of digits.", "O(n)", "O(1)"),
  (69, "Sqrt(x)", "easy", ["Math", "Binary Search"],
   "Given a non-negative integer `x`, return the square root of `x` rounded down to the nearest integer. The returned integer should be non-negative as well. You must not use any built-in exponent function or operator.", "O(log n)", "O(1)"),
  (70, "Climbing Stairs", "easy", ["Math", "Dynamic Programming"],
   "You are climbing a staircase. It takes `n` steps to reach the top. Each time you can either climb 1 or 2 steps. In how many distinct ways can you climb to the top?", "O(n)", "O(1)"),
  (71, "Simplify Path", "medium", ["Strings", "Stack"],
   "Given an absolute path for a Unix-style file system, which begins with a slash '/', transform this absolute path into its simplified canonical path.", "O(n)", "O(n)"),
  (73, "Set Matrix Zeroes", "medium", ["Arrays", "Hash Table", "Matrix"],
   "Given an `m x n` integer matrix, if an element is 0, set its entire row and column to 0's. You must do it in place.", "O(m*n)", "O(1)"),
  (74, "Search a 2D Matrix", "medium", ["Arrays", "Binary Search", "Matrix"],
   "You are given an `m x n` integer matrix with specific sorted properties. Write an efficient algorithm that searches for a value `target` in this matrix.", "O(log(m*n))", "O(1)"),
  (75, "Sort Colors", "medium", ["Arrays", "Two Pointers", "Sorting"],
   "Given an array `nums` with `n` objects colored red, white, or blue, sort them in-place so that objects of the same color are adjacent, with the colors in the order red (0), white (1), and blue (2). You must solve this problem without using the library's sort function.", "O(n)", "O(1)"),
  (76, "Minimum Window Substring", "hard", ["Strings", "Hash Table", "Sliding Window"],
   "Given two strings `s` and `t` of lengths `m` and `n` respectively, return the minimum window substring of `s` such that every character in `t` (including duplicates) is included in the window.", "O(m+n)", "O(m+n)"),
  (78, "Subsets", "medium", ["Arrays", "Backtracking", "Bit Manipulation"],
   "Given an integer array `nums` of unique elements, return all possible subsets (the power set). The solution set must not contain duplicate subsets. Return the solution in any order.", "O(n*2^n)", "O(n)"),
  (79, "Word Search", "medium", ["Arrays", "Backtracking", "Matrix"],
   "Given an `m x n` grid of characters `board` and a string `word`, return `true` if `word` exists in the grid. The word can be constructed from letters of sequentially adjacent cells (horizontally or vertically neighboring).", "O(m*n*4^L)", "O(L)"),
  (84, "Largest Rectangle in Histogram", "hard", ["Arrays", "Stack"],
   "Given an array of integers `heights` representing the histogram's bar height where the width of each bar is 1, return the area of the largest rectangle in the histogram.", "O(n)", "O(n)"),
  (88, "Merge Sorted Array", "easy", ["Arrays", "Two Pointers", "Sorting"],
   "You are given two integer arrays `nums1` and `nums2`, sorted in non-decreasing order, and two integers `m` and `n`, representing the number of elements in `nums1` and `nums2` respectively. Merge `nums2` into `nums1` as one sorted array.", "O(m+n)", "O(1)"),
  (90, "Subsets II", "medium", ["Arrays", "Backtracking", "Bit Manipulation"],
   "Given an integer array `nums` that may contain duplicates, return all possible subsets (the power set). The solution set must not contain duplicate subsets. Return the solution in any order.", "O(n*2^n)", "O(n)"),
  (94, "Binary Tree Inorder Traversal", "easy", ["Trees", "Stack", "Recursion"],
   "Given the root of a binary tree, return the inorder traversal of its nodes' values.", "O(n)", "O(n)"),
  (98, "Validate Binary Search Tree", "medium", ["Trees", "Binary Search", "Recursion"],
   "Given the root of a binary tree, determine if it is a valid binary search tree (BST).", "O(n)", "O(n)"),
  (100, "Same Tree", "easy", ["Trees", "Recursion"],
   "Given the roots of two binary trees `p` and `q`, write a function to check if they are the same or not. Two binary trees are considered the same if they are structurally identical, and the nodes have the same value.", "O(n)", "O(n)"),
  (101, "Symmetric Tree", "easy", ["Trees", "Recursion"],
   "Given the root of a binary tree, check whether it is a mirror of itself (i.e., symmetric around its center).", "O(n)", "O(n)"),
  (102, "Binary Tree Level Order Traversal", "medium", ["Trees", "Queue"],
   "Given the root of a binary tree, return the level order traversal of its nodes' values (i.e., from left to right, level by level).", "O(n)", "O(n)"),
  (104, "Maximum Depth of Binary Tree", "easy", ["Trees", "Recursion"],
   "Given the root of a binary tree, return its maximum depth. A binary tree's maximum depth is the number of nodes along the longest path from the root node down to the farthest leaf node.", "O(n)", "O(n)"),
  (105, "Construct Binary Tree from Preorder and Inorder Traversal", "medium", ["Trees", "Hash Table", "Recursion"],
   "Given two integer arrays `preorder` and `inorder` where `preorder` is the preorder traversal of a binary tree and `inorder` is the inorder traversal of the same tree, construct and return the binary tree.", "O(n)", "O(n)"),
  (108, "Convert Sorted Array to Binary Search Tree", "easy", ["Trees", "Binary Search", "Recursion"],
   "Given an integer array `nums` where the elements are sorted in ascending order, convert it to a height-balanced binary search tree.", "O(n)", "O(log n)"),
  (110, "Balanced Binary Tree", "easy", ["Trees", "Recursion"],
   "Given a binary tree, determine if it is height-balanced. A height-balanced binary tree is a binary tree in which the depth of the two subtrees of every node never differs by more than one.", "O(n)", "O(n)"),
  (112, "Path Sum", "easy", ["Trees", "Recursion"],
   "Given the root of a binary tree and an integer `targetSum`, return `true` if the tree has a root-to-leaf path such that adding up all the values along the path equals `targetSum`.", "O(n)", "O(n)"),
  (121, "Best Time to Buy and Sell Stock", "easy", ["Arrays", "Dynamic Programming"],
   "You are given an array `prices` where `prices[i]` is the price of a given stock on the i-th day. You want to maximize your profit by choosing a single day to buy one stock and choosing a different day in the future to sell that stock. Return the maximum profit you can achieve from this transaction. If you cannot achieve any profit, return 0.", "O(n)", "O(1)"),
  (122, "Best Time to Buy and Sell Stock II", "medium", ["Arrays", "Dynamic Programming", "Greedy"],
   "You are given an integer array `prices` where `prices[i]` is the price of a given stock on the i-th day. On each day, you may decide to buy and/or sell the stock. Find and return the maximum profit you can achieve. You may hold at most one share at any time.", "O(n)", "O(1)"),
  (124, "Binary Tree Maximum Path Sum", "hard", ["Trees", "Dynamic Programming", "Recursion"],
   "A path in a binary tree is a sequence of nodes where each pair of adjacent nodes in the sequence has an edge connecting them. Given the root of a binary tree, return the maximum path sum of any non-empty path.", "O(n)", "O(n)"),
  (125, "Valid Palindrome", "easy", ["Strings", "Two Pointers"],
   "A phrase is a palindrome if, after converting all uppercase letters into lowercase letters and removing all non-alphanumeric characters, it reads the same forward and backward. Given a string `s`, return `true` if it is a palindrome, or `false` otherwise.", "O(n)", "O(1)"),
  (128, "Longest Consecutive Sequence", "medium", ["Arrays", "Hash Table"],
   "Given an unsorted array of integers `nums`, return the length of the longest consecutive elements sequence. You must write an algorithm that runs in O(n) time.", "O(n)", "O(n)"),
  (130, "Surrounded Regions", "medium", ["Arrays", "Graphs", "Matrix"],
   "Given an `m x n` matrix board containing `'X'` and `'O'`, capture all regions that are 4-directionally surrounded by `'X'`. A region is captured by flipping all `'O's` into `'X's` in that surrounded region.", "O(m*n)", "O(m*n)"),
  (131, "Palindrome Partitioning", "medium", ["Strings", "Dynamic Programming", "Backtracking"],
   "Given a string `s`, partition `s` such that every substring of the partition is a palindrome. Return all possible palindrome partitioning of `s`.", "O(n*2^n)", "O(n)"),
  (133, "Clone Graph", "medium", ["Hash Table", "Graphs"],
   "Given a reference of a node in a connected undirected graph, return a deep copy (clone) of the graph.", "O(V+E)", "O(V)"),
  (136, "Single Number", "easy", ["Arrays", "Bit Manipulation"],
   "Given a non-empty array of integers nums, every element appears twice except for one. Find that single one. You must implement a solution with a linear runtime complexity and use only constant extra space.", "O(n)", "O(1)"),
  (138, "Copy List with Random Pointer", "medium", ["Linked List", "Hash Table"],
   "A linked list of length `n` is given such that each node contains an additional random pointer, which could point to any node in the list, or `null`. Construct a deep copy of the list.", "O(n)", "O(n)"),
  (139, "Word Break", "medium", ["Strings", "Dynamic Programming", "Hash Table"],
   "Given a string `s` and a dictionary of strings `wordDict`, return `true` if `s` can be segmented into a space-separated sequence of one or more dictionary words.", "O(n^2)", "O(n)"),
  (141, "Linked List Cycle", "easy", ["Linked List", "Two Pointers"],
   "Given `head`, the head of a linked list, determine if the linked list has a cycle in it.", "O(n)", "O(1)"),
  (142, "Linked List Cycle II", "medium", ["Linked List", "Two Pointers"],
   "Given the head of a linked list, return the node where the cycle begins. If there is no cycle, return null.", "O(n)", "O(1)"),
  (144, "Binary Tree Preorder Traversal", "easy", ["Trees", "Stack", "Recursion"],
   "Given the root of a binary tree, return the preorder traversal of its nodes' values.", "O(n)", "O(n)"),
  (145, "Binary Tree Postorder Traversal", "easy", ["Trees", "Stack", "Recursion"],
   "Given the root of a binary tree, return the postorder traversal of its nodes' values.", "O(n)", "O(n)"),
  (146, "LRU Cache", "medium", ["Hash Table", "Linked List"],
   "Design a data structure that follows the constraints of a Least Recently Used (LRU) cache. Implement the `LRUCache` class with `get` and `put` methods that run in O(1) average time complexity.", "O(1)", "O(capacity)"),
  (148, "Sort List", "medium", ["Linked List", "Sorting"],
   "Given the head of a linked list, return the list after sorting it in ascending order.", "O(n log n)", "O(log n)"),
  (150, "Evaluate Reverse Polish Notation", "medium", ["Arrays", "Stack", "Math"],
   "You are given an array of strings tokens that represents an arithmetic expression in a Reverse Polish Notation. Evaluate the expression. Return an integer that represents the value of the expression.", "O(n)", "O(n)"),
  (152, "Maximum Product Subarray", "medium", ["Arrays", "Dynamic Programming"],
   "Given an integer array `nums`, find a subarray that has the largest product, and return the product.", "O(n)", "O(1)"),
  (153, "Find Minimum in Rotated Sorted Array", "medium", ["Arrays", "Binary Search"],
   "Suppose an array of length `n` sorted in ascending order is rotated between 1 and `n` times. Given the sorted rotated array `nums` of unique elements, return the minimum element of this array. You must write an algorithm that runs in O(log n) time.", "O(log n)", "O(1)"),
  (155, "Min Stack", "medium", ["Stack"],
   "Design a stack that supports push, pop, top, and retrieving the minimum element in constant time.", "O(1)", "O(n)"),
  (160, "Intersection of Two Linked Lists", "easy", ["Linked List", "Two Pointers"],
   "Given the heads of two singly linked-lists `headA` and `headB`, return the node at which the two lists intersect. If the two linked lists have no intersection at all, return `null`.", "O(m+n)", "O(1)"),
  (162, "Find Peak Element", "medium", ["Arrays", "Binary Search"],
   "A peak element is an element that is strictly greater than its neighbors. Given a 0-indexed integer array `nums`, find a peak element, and return its index. If the array contains multiple peaks, return the index to any of the peaks.", "O(log n)", "O(1)"),
  (167, "Two Sum II - Input Array Is Sorted", "medium", ["Arrays", "Two Pointers", "Binary Search"],
   "Given a 1-indexed array of integers `numbers` that is already sorted in non-decreasing order, find two numbers such that they add up to a specific `target` number.", "O(n)", "O(1)"),
  (169, "Majority Element", "easy", ["Arrays", "Hash Table", "Sorting"],
   "Given an array `nums` of size `n`, return the majority element. The majority element is the element that appears more than ⌊n / 2⌋ times. You may assume that the majority element always exists in the array.", "O(n)", "O(1)"),
  (189, "Rotate Array", "medium", ["Arrays", "Math", "Two Pointers"],
   "Given an integer array `nums`, rotate the array to the right by `k` steps, where `k` is non-negative.", "O(n)", "O(1)"),
  (190, "Reverse Bits", "easy", ["Bit Manipulation"],
   "Reverse bits of a given 32 bits unsigned integer.", "O(1)", "O(1)"),
  (191, "Number of 1 Bits", "easy", ["Bit Manipulation"],
   "Write a function that takes the binary representation of a positive integer and returns the number of set bits it has (also known as the Hamming weight).", "O(1)", "O(1)"),
  (198, "House Robber", "medium", ["Arrays", "Dynamic Programming"],
   "You are a professional robber planning to rob houses along a street. Each house has a certain amount of money stashed. Adjacent houses have security systems connected and it will automatically contact the police if two adjacent houses were broken into on the same night. Given an integer array `nums` representing the amount of money of each house, return the maximum amount of money you can rob tonight without alerting the police.", "O(n)", "O(1)"),
  (200, "Number of Islands", "medium", ["Arrays", "Graphs", "Matrix"],
   "Given an `m x n` 2D binary grid `grid` which represents a map of '1's (land) and '0's (water), return the number of islands. An island is surrounded by water and is formed by connecting adjacent lands horizontally or vertically.", "O(m*n)", "O(m*n)"),
  (206, "Reverse Linked List", "easy", ["Linked List", "Recursion"],
   "Given the head of a singly linked list, reverse the list, and return the reversed list.", "O(n)", "O(1)"),
  (207, "Course Schedule", "medium", ["Graphs"],
   "There are a total of `numCourses` courses you have to take, labeled from `0` to `numCourses - 1`. You are given an array `prerequisites` where `prerequisites[i] = [ai, bi]` indicates that you must take course `bi` first if you want to take course `ai`. Return `true` if you can finish all courses. Otherwise, return `false`.", "O(V+E)", "O(V+E)"),
  (208, "Implement Trie (Prefix Tree)", "medium", ["Strings", "Hash Table"],
   "A trie (pronounced as 'try') or prefix tree is a tree data structure used to efficiently store and retrieve keys in a dataset of strings. Implement the Trie class.", "O(m)", "O(m)"),
  (210, "Course Schedule II", "medium", ["Graphs"],
   "There are a total of `numCourses` courses you have to take, labeled from `0` to `numCourses - 1`. Return the ordering of courses you should take to finish all courses. If it is impossible to finish all courses, return an empty array.", "O(V+E)", "O(V+E)"),
  (215, "Kth Largest Element in an Array", "medium", ["Arrays", "Heap", "Sorting"],
   "Given an integer array `nums` and an integer `k`, return the kth largest element in the array. Note that it is the kth largest element in the sorted order, not the kth distinct element.", "O(n)", "O(1)"),
  (217, "Contains Duplicate", "easy", ["Arrays", "Hash Table", "Sorting"],
   "Given an integer array `nums`, return `true` if any value appears at least twice in the array, and return `false` if every element is distinct.", "O(n)", "O(n)"),
  (226, "Invert Binary Tree", "easy", ["Trees", "Recursion"],
   "Given the root of a binary tree, invert the tree, and return its root.", "O(n)", "O(n)"),
  (230, "Kth Smallest Element in a BST", "medium", ["Trees", "Binary Search"],
   "Given the root of a binary search tree, and an integer `k`, return the kth smallest value (1-indexed) of all the values of the nodes in the tree.", "O(H+k)", "O(H)"),
  (234, "Palindrome Linked List", "easy", ["Linked List", "Two Pointers", "Stack"],
   "Given the head of a singly linked list, return `true` if it is a palindrome or `false` otherwise.", "O(n)", "O(1)"),
  (235, "Lowest Common Ancestor of a Binary Search Tree", "medium", ["Trees", "Binary Search"],
   "Given a binary search tree (BST), find the lowest common ancestor (LCA) node of two given nodes in the BST.", "O(H)", "O(1)"),
  (236, "Lowest Common Ancestor of a Binary Tree", "medium", ["Trees", "Recursion"],
   "Given a binary tree, find the lowest common ancestor (LCA) of two given nodes in the tree.", "O(n)", "O(n)"),
  (238, "Product of Array Except Self", "medium", ["Arrays"],
   "Given an integer array `nums`, return an array `answer` such that `answer[i]` is equal to the product of all the elements of `nums` except `nums[i]`. You must write an algorithm that runs in O(n) time and without using the division operation.", "O(n)", "O(1)"),
  (239, "Sliding Window Maximum", "hard", ["Arrays", "Queue", "Sliding Window", "Heap"],
   "You are given an array of integers `nums`, there is a sliding window of size `k` which is moving from the very left of the array to the very right. You can only see the `k` numbers in the window. Each time the sliding window moves right by one position. Return the max sliding window.", "O(n)", "O(k)"),
  (240, "Search a 2D Matrix II", "medium", ["Arrays", "Binary Search", "Matrix"],
   "Write an efficient algorithm that searches for a value `target` in an `m x n` integer matrix. Integers in each row are sorted in ascending from left to right. Integers in each column are sorted in ascending from top to bottom.", "O(m+n)", "O(1)"),
  (242, "Valid Anagram", "easy", ["Strings", "Hash Table", "Sorting"],
   "Given two strings `s` and `t`, return `true` if `t` is an anagram of `s`, and `false` otherwise.", "O(n)", "O(1)"),
  (268, "Missing Number", "easy", ["Arrays", "Math", "Bit Manipulation"],
   "Given an array `nums` containing `n` distinct numbers in the range `[0, n]`, return the only number in the range that is missing from the array.", "O(n)", "O(1)"),
  (283, "Move Zeroes", "easy", ["Arrays", "Two Pointers"],
   "Given an integer array `nums`, move all 0's to the end of it while maintaining the relative order of the non-zero elements. Note that you must do this in-place without making a copy of the array.", "O(n)", "O(1)"),
  (287, "Find the Duplicate Number", "medium", ["Arrays", "Two Pointers", "Binary Search"],
   "Given an array of integers `nums` containing `n + 1` integers where each integer is in the range `[1, n]` inclusive. There is only one repeated number in `nums`, return this repeated number. You must solve the problem without modifying the array `nums` and using only constant extra space.", "O(n)", "O(1)"),
  (295, "Find Median from Data Stream", "hard", ["Heap", "Sorting"],
   "The median is the middle value in an ordered integer list. Implement the MedianFinder class that can add numbers and find the median efficiently.", "O(log n)", "O(n)"),
  (297, "Serialize and Deserialize Binary Tree", "hard", ["Trees", "Strings"],
   "Design an algorithm to serialize and deserialize a binary tree. There is no restriction on how your serialization/deserialization algorithm should work.", "O(n)", "O(n)"),
  (300, "Longest Increasing Subsequence", "medium", ["Arrays", "Dynamic Programming", "Binary Search"],
   "Given an integer array `nums`, return the length of the longest strictly increasing subsequence.", "O(n log n)", "O(n)"),
  (322, "Coin Change", "medium", ["Arrays", "Dynamic Programming"],
   "You are given an integer array `coins` representing coins of different denominations and an integer `amount` representing a total amount of money. Return the fewest number of coins that you need to make up that amount. If that amount of money cannot be made up by any combination of the coins, return `-1`.", "O(n*amount)", "O(amount)"),
  (338, "Counting Bits", "easy", ["Dynamic Programming", "Bit Manipulation"],
   "Given an integer `n`, return an array `ans` of length `n + 1` such that for each `i` (0 <= i <= n), `ans[i]` is the number of 1's in the binary representation of `i`.", "O(n)", "O(1)"),
  (347, "Top K Frequent Elements", "medium", ["Arrays", "Hash Table", "Heap", "Sorting"],
   "Given an integer array `nums` and an integer `k`, return the `k` most frequent elements. You may return the answer in any order.", "O(n)", "O(n)"),
  (394, "Decode String", "medium", ["Strings", "Stack", "Recursion"],
   "Given an encoded string, return its decoded string. The encoding rule is: `k[encoded_string]`, where the `encoded_string` inside the square brackets is being repeated exactly `k` times.", "O(n)", "O(n)"),
  (416, "Partition Equal Subset Sum", "medium", ["Arrays", "Dynamic Programming"],
   "Given an integer array `nums`, return `true` if you can partition the array into two subsets such that the sum of the elements in both subsets is equal or `false` otherwise.", "O(n*sum)", "O(sum)"),
  (437, "Path Sum III", "medium", ["Trees", "Hash Table", "Recursion"],
   "Given the root of a binary tree and an integer `targetSum`, return the number of paths where the sum of the values along the path equals `targetSum`. The path does not need to start or end at the root or a leaf.", "O(n)", "O(n)"),
  (543, "Diameter of Binary Tree", "easy", ["Trees", "Recursion"],
   "Given the root of a binary tree, return the length of the diameter of the tree. The diameter of a binary tree is the length of the longest path between any two nodes in a tree.", "O(n)", "O(n)"),
  (560, "Subarray Sum Equals K", "medium", ["Arrays", "Hash Table"],
   "Given an array of integers `nums` and an integer `k`, return the total number of subarrays whose sum equals to `k`.", "O(n)", "O(n)"),
  (572, "Subtree of Another Tree", "easy", ["Trees", "Recursion"],
   "Given the roots of two binary trees `root` and `subRoot`, return `true` if there is a subtree of `root` with the same structure and node values of `subRoot` and `false` otherwise.", "O(m*n)", "O(n)"),
  (647, "Palindromic Substrings", "medium", ["Strings", "Dynamic Programming"],
   "Given a string `s`, return the number of palindromic substrings in it. A string is a palindrome when it reads the same backward as forward. A substring is a contiguous sequence of characters within the string.", "O(n^2)", "O(1)"),
  (695, "Max Area of Island", "medium", ["Arrays", "Graphs", "Matrix"],
   "You are given an `m x n` binary matrix `grid`. An island is a group of 1's connected 4-directionally. Return the maximum area of an island in `grid`. If there is no island, return 0.", "O(m*n)", "O(m*n)"),
  (739, "Daily Temperatures", "medium", ["Arrays", "Stack"],
   "Given an array of integers `temperatures` represents the daily temperatures, return an array `answer` such that `answer[i]` is the number of days you have to wait after the i-th day to get a warmer temperature.", "O(n)", "O(n)"),
  (763, "Partition Labels", "medium", ["Strings", "Hash Table", "Two Pointers", "Greedy"],
   "You are given a string `s`. We want to partition the string into as many parts as possible so that each letter appears in at most one part. Return a list of integers representing the size of these parts.", "O(n)", "O(1)"),
]


def get_templates(title, func_name):
    """Generate starter + solution code templates for all 5 languages."""
    return {
        "python3": (
            f"class Solution:\n    def {func_name}(self, *args):\n        # Write your solution here\n        pass",
            f"class Solution:\n    def {func_name}(self, *args):\n        # TODO: Implement solution for {title}\n        pass"
        ),
        "cpp17": (
            f"#include <vector>\n#include <string>\n#include <unordered_map>\nusing namespace std;\n\nclass Solution {{\npublic:\n    // Write your solution here\n    void {func_name}() {{\n        \n    }}\n}};",
            f"class Solution {{\npublic:\n    void {func_name}() {{\n        // TODO: Implement solution for {title}\n    }}\n}};"
        ),
        "java": (
            f"import java.util.*;\n\nclass Solution {{\n    // Write your solution here\n    public void {func_name}() {{\n        \n    }}\n}}",
            f"class Solution {{\n    public void {func_name}() {{\n        // TODO: Implement solution for {title}\n    }}\n}}"
        ),
        "javascript": (
            f"/**\n * Write your solution here\n */\nvar {func_name} = function() {{\n    \n}};",
            f"var {func_name} = function() {{\n    // TODO: Implement solution for {title}\n}};"
        ),
        "c": (
            f"#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n\n// Write your solution here\nvoid {func_name}() {{\n    \n}}",
            f"void {func_name}() {{\n    // TODO: Implement solution for {title}\n}}"
        ),
    }


def make_func_name(title):
    """Convert problem title to camelCase function name."""
    words = title.replace("(", "").replace(")", "").replace("-", " ").replace(",", "").split()
    if not words:
        return "solve"
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


class Command(BaseCommand):
    help = "Seed 100+ LeetCode-style coding problems"

    def handle(self, *args, **options):
        self.stdout.write("Seeding topics...")
        topic_map = {}
        for name, desc in TOPICS:
            t, _ = Topic.objects.get_or_create(name=name, defaults={"description": desc})
            topic_map[name] = t

        self.stdout.write("Seeding companies...")
        company_map = {}
        for name in COMPANIES:
            c, _ = Company.objects.get_or_create(name=name)
            company_map[name] = c

        # Seed fully detailed problems (Problems 1-2)
        for data in PROBLEMS:
            num, title, diff, topics, companies, desc, constr, ex_in, ex_out, ex_expl, hints, tc, sc, tests, templates = data
            self._create_problem(num, title, diff, topics, companies, desc, constr,
                                 ex_in, ex_out, ex_expl, hints, tc, sc, tests, templates,
                                 topic_map, company_map)

        # Seed compact problems with generated templates
        assigned_companies = list(COMPANIES)
        for i, data in enumerate(COMPACT_PROBLEMS):
            num, title, diff, topics, desc, tc, sc = data
            # Assign 2-3 companies round-robin
            cos = [assigned_companies[i % len(assigned_companies)],
                   assigned_companies[(i + 3) % len(assigned_companies)]]
            func_name = make_func_name(title)
            templates = get_templates(title, func_name)

            # Generate generic test cases
            tests = [
                ("# See problem description for input format", "# Expected output", True, "Sample test case"),
                ("# Test case 2", "# Expected output 2", False, "Additional test case"),
            ]

            # Generate constraints
            constr = "See problem description for detailed constraints."
            hints = f"Think about the most efficient approach.\nConsider edge cases."

            self._create_problem(
                num, title, diff, topics, cos, desc, constr,
                "See examples in description", "See examples in description",
                "", hints, tc, sc, tests, templates, topic_map, company_map
            )

        total = Problem.objects.count()
        self.stdout.write(self.style.SUCCESS(f"\nDone! Total problems in database: {total}"))

    def _create_problem(self, num, title, diff, topics, companies, desc, constr,
                        ex_in, ex_out, ex_expl, hints, tc, sc, tests, templates,
                        topic_map, company_map):
        p, created = Problem.objects.get_or_create(
            problem_number=num,
            defaults={
                "title": title,
                "difficulty": diff,
                "description": desc,
                "constraints": constr,
                "example_input": ex_in,
                "example_output": ex_out,
                "example_explanation": ex_expl,
                "hints": hints,
                "time_complexity": tc,
                "space_complexity": sc,
            }
        )

        if not created:
            self.stdout.write(f"  Skipping #{num} {title} (exists)")
            return

        # Add topics
        for t_name in topics:
            if t_name in topic_map:
                p.topics.add(topic_map[t_name])

        # Add companies
        for c_name in companies:
            if c_name in company_map:
                p.companies.add(company_map[c_name])

        # Add test cases
        for order, (inp, out, is_sample, expl) in enumerate(tests):
            TestCase.objects.create(
                problem=p, input_data=inp, expected_output=out,
                is_sample=is_sample, explanation=expl, order=order
            )

        # Add code templates
        for lang, (starter, solution) in templates.items():
            CodeTemplate.objects.create(
                problem=p, language=lang,
                template_code=starter, solution_code=solution
            )

        self.stdout.write(f"  ✓ #{num} {title} ({diff})")
