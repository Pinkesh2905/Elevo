"""Problems 1-10: Foundational problems."""

PROBLEMS = [
    {
        "number": 1,
        "title": "Two Sum",
        "difficulty": "easy",
        "topics": ["Arrays", "Hash Table"],
        "companies": ["Google", "Amazon", "Meta"],
        "description": "Given an array of integers `nums` and an integer `target`, return indices of the two numbers such that they add up to `target`.\n\nYou may assume that each input would have exactly one solution, and you may not use the same element twice.\n\nYou can return the answer in any order.",
        "constraints": "2 <= nums.length <= 10^4\n-10^9 <= nums[i] <= 10^9\n-10^9 <= target <= 10^9\nOnly one valid answer exists.",
        "example_input": "nums = [2,7,11,15], target = 9",
        "example_output": "[0,1]",
        "example_explanation": "Because nums[0] + nums[1] == 9, we return [0, 1].",
        "hints": "Try using a hash map to store seen values.\nFor each number, check if target - number exists in the map.",
        "time_complexity": "O(n)",
        "space_complexity": "O(n)",
        "test_cases": [
            {"input": "nums = [2,7,11,15]\ntarget = 9", "output": "[0, 1]", "is_sample": True, "explanation": "2 + 7 = 9"},
            {"input": "nums = [3,2,4]\ntarget = 6", "output": "[1, 2]", "is_sample": True, "explanation": "2 + 4 = 6"},
            {"input": "nums = [3,3]\ntarget = 6", "output": "[0, 1]", "is_sample": False, "explanation": "3 + 3 = 6"},
        ],
        "templates": {
            "python3": {
                "starter": "class Solution:\n    def twoSum(self, nums: list[int], target: int) -> list[int]:\n        # Write your solution here\n        pass",
                "solution": "class Solution:\n    def twoSum(self, nums: list[int], target: int) -> list[int]:\n        seen = {}\n        for i, n in enumerate(nums):\n            comp = target - n\n            if comp in seen:\n                return [seen[comp], i]\n            seen[n] = i\n        return []"
            },
            "cpp17": {
                "starter": "#include <vector>\n#include <unordered_map>\nusing namespace std;\n\nclass Solution {\npublic:\n    vector<int> twoSum(vector<int>& nums, int target) {\n        // Write your solution here\n        return {};\n    }\n};",
                "solution": "#include <vector>\n#include <unordered_map>\nusing namespace std;\n\nclass Solution {\npublic:\n    vector<int> twoSum(vector<int>& nums, int target) {\n        unordered_map<int,int> seen;\n        for (int i = 0; i < nums.size(); i++) {\n            int comp = target - nums[i];\n            if (seen.count(comp)) return {seen[comp], i};\n            seen[nums[i]] = i;\n        }\n        return {};\n    }\n};"
            },
            "java": {
                "starter": "import java.util.*;\n\nclass Solution {\n    public int[] twoSum(int[] nums, int target) {\n        // Write your solution here\n        return new int[]{};\n    }\n}",
                "solution": "import java.util.*;\n\nclass Solution {\n    public int[] twoSum(int[] nums, int target) {\n        Map<Integer,Integer> seen = new HashMap<>();\n        for (int i = 0; i < nums.length; i++) {\n            int comp = target - nums[i];\n            if (seen.containsKey(comp)) return new int[]{seen.get(comp), i};\n            seen.put(nums[i], i);\n        }\n        return new int[]{};\n    }\n}"
            },
            "javascript": {
                "starter": "/**\n * @param {number[]} nums\n * @param {number} target\n * @return {number[]}\n */\nvar twoSum = function(nums, target) {\n    // Write your solution here\n};",
                "solution": "var twoSum = function(nums, target) {\n    const seen = new Map();\n    for (let i = 0; i < nums.length; i++) {\n        const comp = target - nums[i];\n        if (seen.has(comp)) return [seen.get(comp), i];\n        seen.set(nums[i], i);\n    }\n    return [];\n};"
            },
            "c": {
                "starter": "#include <stdlib.h>\n\nint* twoSum(int* nums, int numsSize, int target, int* returnSize) {\n    *returnSize = 2;\n    int* result = (int*)malloc(2 * sizeof(int));\n    // Write your solution here\n    return result;\n}",
                "solution": "#include <stdlib.h>\n\nint* twoSum(int* nums, int numsSize, int target, int* returnSize) {\n    *returnSize = 2;\n    int* result = (int*)malloc(2 * sizeof(int));\n    for (int i = 0; i < numsSize; i++)\n        for (int j = i + 1; j < numsSize; j++)\n            if (nums[i] + nums[j] == target) {\n                result[0] = i; result[1] = j; return result;\n            }\n    return result;\n}"
            },
        },
    },
    {
        "number": 2,
        "title": "Add Two Numbers",
        "difficulty": "medium",
        "topics": ["Linked List", "Math"],
        "companies": ["Amazon", "Microsoft", "Bloomberg"],
        "description": "You are given two non-empty linked lists representing two non-negative integers. The digits are stored in reverse order, and each of their nodes contains a single digit. Add the two numbers and return the sum as a linked list.\n\nYou may assume the two numbers do not contain any leading zero, except the number 0 itself.",
        "constraints": "The number of nodes in each linked list is in the range [1, 100].\n0 <= Node.val <= 9\nIt is guaranteed that the list represents a number that does not have leading zeros.",
        "example_input": "l1 = [2,4,3], l2 = [5,6,4]",
        "example_output": "[7,0,8]",
        "example_explanation": "342 + 465 = 807.",
        "hints": "Simulate digit-by-digit addition from head to tail.\nDon't forget the carry at the end!",
        "time_complexity": "O(max(m,n))",
        "space_complexity": "O(max(m,n))",
        "test_cases": [
            {"input": "l1 = [2,4,3]\nl2 = [5,6,4]", "output": "[7,0,8]", "is_sample": True, "explanation": "342 + 465 = 807"},
            {"input": "l1 = [0]\nl2 = [0]", "output": "[0]", "is_sample": True, "explanation": "0 + 0 = 0"},
            {"input": "l1 = [9,9,9,9]\nl2 = [9,9,9]", "output": "[8,9,9,0,1]", "is_sample": False, "explanation": "9999 + 999 = 10998"},
        ],
        "templates": {
            "python3": {
                "starter": "class ListNode:\n    def __init__(self, val=0, next=None):\n        self.val = val\n        self.next = next\n\nclass Solution:\n    def addTwoNumbers(self, l1: ListNode, l2: ListNode) -> ListNode:\n        # Write your solution here\n        pass",
                "solution": "class Solution:\n    def addTwoNumbers(self, l1: ListNode, l2: ListNode) -> ListNode:\n        dummy = ListNode(0)\n        cur, carry = dummy, 0\n        while l1 or l2 or carry:\n            v1 = l1.val if l1 else 0\n            v2 = l2.val if l2 else 0\n            s = v1 + v2 + carry\n            carry, val = divmod(s, 10)\n            cur.next = ListNode(val)\n            cur = cur.next\n            l1 = l1.next if l1 else None\n            l2 = l2.next if l2 else None\n        return dummy.next"
            },
            "cpp17": {
                "starter": "struct ListNode {\n    int val;\n    ListNode *next;\n    ListNode(int x) : val(x), next(nullptr) {}\n};\n\nclass Solution {\npublic:\n    ListNode* addTwoNumbers(ListNode* l1, ListNode* l2) {\n        // Write your solution here\n        return nullptr;\n    }\n};",
                "solution": "class Solution {\npublic:\n    ListNode* addTwoNumbers(ListNode* l1, ListNode* l2) {\n        ListNode dummy(0);\n        ListNode* cur = &dummy;\n        int carry = 0;\n        while (l1 || l2 || carry) {\n            int s = carry + (l1 ? l1->val : 0) + (l2 ? l2->val : 0);\n            carry = s / 10;\n            cur->next = new ListNode(s % 10);\n            cur = cur->next;\n            if (l1) l1 = l1->next;\n            if (l2) l2 = l2->next;\n        }\n        return dummy.next;\n    }\n};"
            },
            "java": {
                "starter": "class ListNode {\n    int val;\n    ListNode next;\n    ListNode(int val) { this.val = val; }\n}\n\nclass Solution {\n    public ListNode addTwoNumbers(ListNode l1, ListNode l2) {\n        // Write your solution here\n        return null;\n    }\n}",
                "solution": "class Solution {\n    public ListNode addTwoNumbers(ListNode l1, ListNode l2) {\n        ListNode dummy = new ListNode(0);\n        ListNode cur = dummy;\n        int carry = 0;\n        while (l1 != null || l2 != null || carry != 0) {\n            int s = carry + (l1 != null ? l1.val : 0) + (l2 != null ? l2.val : 0);\n            carry = s / 10;\n            cur.next = new ListNode(s % 10);\n            cur = cur.next;\n            if (l1 != null) l1 = l1.next;\n            if (l2 != null) l2 = l2.next;\n        }\n        return dummy.next;\n    }\n}"
            },
            "javascript": {
                "starter": "function ListNode(val, next) {\n    this.val = (val===undefined ? 0 : val)\n    this.next = (next===undefined ? null : next)\n}\n\nvar addTwoNumbers = function(l1, l2) {\n    // Write your solution here\n};",
                "solution": "var addTwoNumbers = function(l1, l2) {\n    let dummy = new ListNode(0), cur = dummy, carry = 0;\n    while (l1 || l2 || carry) {\n        let s = carry + (l1 ? l1.val : 0) + (l2 ? l2.val : 0);\n        carry = Math.floor(s / 10);\n        cur.next = new ListNode(s % 10);\n        cur = cur.next;\n        if (l1) l1 = l1.next;\n        if (l2) l2 = l2.next;\n    }\n    return dummy.next;\n};"
            },
            "c": {
                "starter": "#include <stdlib.h>\n\nstruct ListNode {\n    int val;\n    struct ListNode *next;\n};\n\nstruct ListNode* addTwoNumbers(struct ListNode* l1, struct ListNode* l2) {\n    // Write your solution here\n    return NULL;\n}",
                "solution": "struct ListNode* addTwoNumbers(struct ListNode* l1, struct ListNode* l2) {\n    struct ListNode dummy = {0, NULL};\n    struct ListNode* cur = &dummy;\n    int carry = 0;\n    while (l1 || l2 || carry) {\n        int s = carry + (l1 ? l1->val : 0) + (l2 ? l2->val : 0);\n        carry = s / 10;\n        cur->next = (struct ListNode*)malloc(sizeof(struct ListNode));\n        cur->next->val = s % 10;\n        cur->next->next = NULL;\n        cur = cur->next;\n        if (l1) l1 = l1->next;\n        if (l2) l2 = l2->next;\n    }\n    return dummy.next;\n}"
            },
        },
    },
    {
        "number": 3,
        "title": "Longest Substring Without Repeating Characters",
        "difficulty": "medium",
        "topics": ["Strings", "Sliding Window", "Hash Table"],
        "companies": ["Amazon", "Google", "Bloomberg"],
        "description": "Given a string `s`, find the length of the longest substring without repeating characters.",
        "constraints": "0 <= s.length <= 5 * 10^4\ns consists of English letters, digits, symbols and spaces.",
        "example_input": 's = "abcabcbb"',
        "example_output": "3",
        "example_explanation": 'The answer is "abc", with the length of 3.',
        "hints": "Use a sliding window approach with two pointers.\nUse a set or hash map to track characters in the current window.",
        "time_complexity": "O(n)",
        "space_complexity": "O(min(n, m))",
        "test_cases": [
            {"input": 's = "abcabcbb"', "output": "3", "is_sample": True, "explanation": "The longest substring is 'abc'"},
            {"input": 's = "bbbbb"', "output": "1", "is_sample": True, "explanation": "The longest substring is 'b'"},
            {"input": 's = "pwwkew"', "output": "3", "is_sample": True, "explanation": "The longest substring is 'wke'"},
            {"input": 's = ""', "output": "0", "is_sample": False, "explanation": "Empty string"},
        ],
        "templates": {
            "python3": {
                "starter": "class Solution:\n    def lengthOfLongestSubstring(self, s: str) -> int:\n        # Write your solution here\n        pass",
                "solution": "class Solution:\n    def lengthOfLongestSubstring(self, s: str) -> int:\n        char_set = set()\n        left = 0\n        result = 0\n        for right in range(len(s)):\n            while s[right] in char_set:\n                char_set.remove(s[left])\n                left += 1\n            char_set.add(s[right])\n            result = max(result, right - left + 1)\n        return result"
            },
            "cpp17": {
                "starter": "#include <string>\n#include <unordered_set>\nusing namespace std;\n\nclass Solution {\npublic:\n    int lengthOfLongestSubstring(string s) {\n        // Write your solution here\n        return 0;\n    }\n};",
                "solution": "class Solution {\npublic:\n    int lengthOfLongestSubstring(string s) {\n        unordered_set<char> charSet;\n        int left = 0, result = 0;\n        for (int right = 0; right < s.size(); right++) {\n            while (charSet.count(s[right])) {\n                charSet.erase(s[left]);\n                left++;\n            }\n            charSet.insert(s[right]);\n            result = max(result, right - left + 1);\n        }\n        return result;\n    }\n};"
            },
            "java": {
                "starter": "import java.util.*;\n\nclass Solution {\n    public int lengthOfLongestSubstring(String s) {\n        // Write your solution here\n        return 0;\n    }\n}",
                "solution": "class Solution {\n    public int lengthOfLongestSubstring(String s) {\n        Set<Character> set = new HashSet<>();\n        int left = 0, result = 0;\n        for (int right = 0; right < s.length(); right++) {\n            while (set.contains(s.charAt(right))) {\n                set.remove(s.charAt(left));\n                left++;\n            }\n            set.add(s.charAt(right));\n            result = Math.max(result, right - left + 1);\n        }\n        return result;\n    }\n}"
            },
            "javascript": {
                "starter": "/**\n * @param {string} s\n * @return {number}\n */\nvar lengthOfLongestSubstring = function(s) {\n    // Write your solution here\n};",
                "solution": "var lengthOfLongestSubstring = function(s) {\n    const set = new Set();\n    let left = 0, result = 0;\n    for (let right = 0; right < s.length; right++) {\n        while (set.has(s[right])) {\n            set.delete(s[left]);\n            left++;\n        }\n        set.add(s[right]);\n        result = Math.max(result, right - left + 1);\n    }\n    return result;\n};"
            },
            "c": {
                "starter": "#include <string.h>\n\nint lengthOfLongestSubstring(char* s) {\n    // Write your solution here\n    return 0;\n}",
                "solution": "int lengthOfLongestSubstring(char* s) {\n    int freq[128] = {0};\n    int left = 0, result = 0, len = strlen(s);\n    for (int right = 0; right < len; right++) {\n        freq[(int)s[right]]++;\n        while (freq[(int)s[right]] > 1) {\n            freq[(int)s[left]]--;\n            left++;\n        }\n        if (right - left + 1 > result) result = right - left + 1;\n    }\n    return result;\n}"
            },
        },
    },
    {
        "number": 4,
        "title": "Median of Two Sorted Arrays",
        "difficulty": "hard",
        "topics": ["Arrays", "Binary Search"],
        "companies": ["Google", "Amazon", "Apple"],
        "description": "Given two sorted arrays `nums1` and `nums2` of size `m` and `n` respectively, return the median of the two sorted arrays.\n\nThe overall run time complexity should be O(log (m+n)).",
        "constraints": "nums1.length == m\nnums2.length == n\n0 <= m <= 1000\n0 <= n <= 1000\n1 <= m + n <= 2000\n-10^6 <= nums1[i], nums2[i] <= 10^6",
        "example_input": "nums1 = [1,3], nums2 = [2]",
        "example_output": "2.00000",
        "example_explanation": "Merged array = [1,2,3] and median is 2.",
        "hints": "Use binary search on the shorter array.\nPartition both arrays such that left half has the same number of elements as right half.",
        "time_complexity": "O(log(min(m,n)))",
        "space_complexity": "O(1)",
        "test_cases": [
            {"input": "nums1 = [1,3]\nnums2 = [2]", "output": "2.0", "is_sample": True, "explanation": "Merged = [1,2,3], median = 2"},
            {"input": "nums1 = [1,2]\nnums2 = [3,4]", "output": "2.5", "is_sample": True, "explanation": "Merged = [1,2,3,4], median = (2+3)/2 = 2.5"},
            {"input": "nums1 = []\nnums2 = [1]", "output": "1.0", "is_sample": False, "explanation": "Only one element"},
        ],
        "templates": {
            "python3": {
                "starter": "class Solution:\n    def findMedianSortedArrays(self, nums1: list[int], nums2: list[int]) -> float:\n        # Write your solution here\n        pass",
                "solution": "class Solution:\n    def findMedianSortedArrays(self, nums1: list[int], nums2: list[int]) -> float:\n        A, B = nums1, nums2\n        if len(A) > len(B):\n            A, B = B, A\n        m, n = len(A), len(B)\n        lo, hi = 0, m\n        while lo <= hi:\n            i = (lo + hi) // 2\n            j = (m + n + 1) // 2 - i\n            left_a = A[i - 1] if i > 0 else float('-inf')\n            right_a = A[i] if i < m else float('inf')\n            left_b = B[j - 1] if j > 0 else float('-inf')\n            right_b = B[j] if j < n else float('inf')\n            if left_a <= right_b and left_b <= right_a:\n                if (m + n) % 2 == 0:\n                    return (max(left_a, left_b) + min(right_a, right_b)) / 2\n                return max(left_a, left_b)\n            elif left_a > right_b:\n                hi = i - 1\n            else:\n                lo = i + 1\n        return 0.0"
            },
            "cpp17": {
                "starter": "#include <vector>\nusing namespace std;\n\nclass Solution {\npublic:\n    double findMedianSortedArrays(vector<int>& nums1, vector<int>& nums2) {\n        // Write your solution here\n        return 0.0;\n    }\n};",
                "solution": "class Solution {\npublic:\n    double findMedianSortedArrays(vector<int>& nums1, vector<int>& nums2) {\n        if (nums1.size() > nums2.size()) swap(nums1, nums2);\n        int m = nums1.size(), n = nums2.size();\n        int lo = 0, hi = m;\n        while (lo <= hi) {\n            int i = (lo + hi) / 2;\n            int j = (m + n + 1) / 2 - i;\n            int la = i > 0 ? nums1[i-1] : INT_MIN;\n            int ra = i < m ? nums1[i] : INT_MAX;\n            int lb = j > 0 ? nums2[j-1] : INT_MIN;\n            int rb = j < n ? nums2[j] : INT_MAX;\n            if (la <= rb && lb <= ra) {\n                if ((m+n) % 2 == 0) return (max(la,lb) + min(ra,rb)) / 2.0;\n                return max(la, lb);\n            } else if (la > rb) hi = i - 1;\n            else lo = i + 1;\n        }\n        return 0.0;\n    }\n};"
            },
            "java": {
                "starter": "class Solution {\n    public double findMedianSortedArrays(int[] nums1, int[] nums2) {\n        // Write your solution here\n        return 0.0;\n    }\n}",
                "solution": "class Solution {\n    public double findMedianSortedArrays(int[] nums1, int[] nums2) {\n        if (nums1.length > nums2.length) return findMedianSortedArrays(nums2, nums1);\n        int m = nums1.length, n = nums2.length;\n        int lo = 0, hi = m;\n        while (lo <= hi) {\n            int i = (lo + hi) / 2;\n            int j = (m + n + 1) / 2 - i;\n            int la = i > 0 ? nums1[i-1] : Integer.MIN_VALUE;\n            int ra = i < m ? nums1[i] : Integer.MAX_VALUE;\n            int lb = j > 0 ? nums2[j-1] : Integer.MIN_VALUE;\n            int rb = j < n ? nums2[j] : Integer.MAX_VALUE;\n            if (la <= rb && lb <= ra) {\n                if ((m+n) % 2 == 0) return (Math.max(la,lb) + Math.min(ra,rb)) / 2.0;\n                return Math.max(la, lb);\n            } else if (la > rb) hi = i - 1;\n            else lo = i + 1;\n        }\n        return 0.0;\n    }\n}"
            },
            "javascript": {
                "starter": "/**\n * @param {number[]} nums1\n * @param {number[]} nums2\n * @return {number}\n */\nvar findMedianSortedArrays = function(nums1, nums2) {\n    // Write your solution here\n};",
                "solution": "var findMedianSortedArrays = function(nums1, nums2) {\n    if (nums1.length > nums2.length) [nums1, nums2] = [nums2, nums1];\n    const m = nums1.length, n = nums2.length;\n    let lo = 0, hi = m;\n    while (lo <= hi) {\n        const i = Math.floor((lo + hi) / 2);\n        const j = Math.floor((m + n + 1) / 2) - i;\n        const la = i > 0 ? nums1[i-1] : -Infinity;\n        const ra = i < m ? nums1[i] : Infinity;\n        const lb = j > 0 ? nums2[j-1] : -Infinity;\n        const rb = j < n ? nums2[j] : Infinity;\n        if (la <= rb && lb <= ra) {\n            if ((m+n) % 2 === 0) return (Math.max(la,lb) + Math.min(ra,rb)) / 2;\n            return Math.max(la, lb);\n        } else if (la > rb) hi = i - 1;\n        else lo = i + 1;\n    }\n    return 0;\n};"
            },
            "c": {
                "starter": "double findMedianSortedArrays(int* nums1, int n1, int* nums2, int n2) {\n    // Write your solution here\n    return 0.0;\n}",
                "solution": "double findMedianSortedArrays(int* nums1, int n1, int* nums2, int n2) {\n    if (n1 > n2) return findMedianSortedArrays(nums2, n2, nums1, n1);\n    int lo = 0, hi = n1;\n    while (lo <= hi) {\n        int i = (lo + hi) / 2;\n        int j = (n1 + n2 + 1) / 2 - i;\n        int la = i > 0 ? nums1[i-1] : -1000001;\n        int ra = i < n1 ? nums1[i] : 1000001;\n        int lb = j > 0 ? nums2[j-1] : -1000001;\n        int rb = j < n2 ? nums2[j] : 1000001;\n        if (la <= rb && lb <= ra) {\n            if ((n1+n2) % 2 == 0) return ((la>lb?la:lb) + (ra<rb?ra:rb)) / 2.0;\n            return la > lb ? la : lb;\n        } else if (la > rb) hi = i - 1;\n        else lo = i + 1;\n    }\n    return 0.0;\n}"
            },
        },
    },
    {
        "number": 5,
        "title": "Longest Palindromic Substring",
        "difficulty": "medium",
        "topics": ["Strings", "Dynamic Programming"],
        "companies": ["Amazon", "Microsoft", "Adobe"],
        "description": "Given a string `s`, return the longest palindromic substring in `s`.",
        "constraints": "1 <= s.length <= 1000\ns consist of only digits and English letters.",
        "example_input": 's = "babad"',
        "example_output": '"bab"',
        "example_explanation": '"aba" is also a valid answer.',
        "hints": "Expand around each center (each character + each pair of adjacent characters).\nA palindrome mirrors around its center.",
        "time_complexity": "O(n^2)",
        "space_complexity": "O(1)",
        "test_cases": [
            {"input": 's = "babad"', "output": '"bab"', "is_sample": True, "explanation": "'aba' is also valid"},
            {"input": 's = "cbbd"', "output": '"bb"', "is_sample": True, "explanation": "Longest palindrome is 'bb'"},
            {"input": 's = "a"', "output": '"a"', "is_sample": False, "explanation": "Single char is a palindrome"},
        ],
        "templates": {
            "python3": {
                "starter": "class Solution:\n    def longestPalindrome(self, s: str) -> str:\n        # Write your solution here\n        pass",
                "solution": "class Solution:\n    def longestPalindrome(self, s: str) -> str:\n        res = ''\n        for i in range(len(s)):\n            for l, r in [(i, i), (i, i + 1)]:\n                while l >= 0 and r < len(s) and s[l] == s[r]:\n                    if r - l + 1 > len(res):\n                        res = s[l:r+1]\n                    l -= 1\n                    r += 1\n        return res"
            },
            "cpp17": {
                "starter": "#include <string>\nusing namespace std;\n\nclass Solution {\npublic:\n    string longestPalindrome(string s) {\n        // Write your solution here\n        return \"\";\n    }\n};",
                "solution": "class Solution {\npublic:\n    string longestPalindrome(string s) {\n        int start = 0, maxLen = 0;\n        for (int i = 0; i < s.size(); i++) {\n            for (int d : {0, 1}) {\n                int l = i, r = i + d;\n                while (l >= 0 && r < s.size() && s[l] == s[r]) { l--; r++; }\n                if (r - l - 1 > maxLen) { start = l + 1; maxLen = r - l - 1; }\n            }\n        }\n        return s.substr(start, maxLen);\n    }\n};"
            },
            "java": {
                "starter": "class Solution {\n    public String longestPalindrome(String s) {\n        // Write your solution here\n        return \"\";\n    }\n}",
                "solution": "class Solution {\n    public String longestPalindrome(String s) {\n        int start = 0, maxLen = 0;\n        for (int i = 0; i < s.length(); i++) {\n            for (int d = 0; d <= 1; d++) {\n                int l = i, r = i + d;\n                while (l >= 0 && r < s.length() && s.charAt(l) == s.charAt(r)) { l--; r++; }\n                if (r - l - 1 > maxLen) { start = l + 1; maxLen = r - l - 1; }\n            }\n        }\n        return s.substring(start, start + maxLen);\n    }\n}"
            },
            "javascript": {
                "starter": "/**\n * @param {string} s\n * @return {string}\n */\nvar longestPalindrome = function(s) {\n    // Write your solution here\n};",
                "solution": "var longestPalindrome = function(s) {\n    let start = 0, maxLen = 0;\n    for (let i = 0; i < s.length; i++) {\n        for (let d of [0, 1]) {\n            let l = i, r = i + d;\n            while (l >= 0 && r < s.length && s[l] === s[r]) { l--; r++; }\n            if (r - l - 1 > maxLen) { start = l + 1; maxLen = r - l - 1; }\n        }\n    }\n    return s.substring(start, start + maxLen);\n};"
            },
            "c": {
                "starter": "#include <string.h>\n#include <stdlib.h>\n\nchar* longestPalindrome(char* s) {\n    // Write your solution here\n    return \"\";\n}",
                "solution": "char* longestPalindrome(char* s) {\n    int n = strlen(s), start = 0, maxLen = 0;\n    for (int i = 0; i < n; i++) {\n        for (int d = 0; d <= 1; d++) {\n            int l = i, r = i + d;\n            while (l >= 0 && r < n && s[l] == s[r]) { l--; r++; }\n            if (r - l - 1 > maxLen) { start = l + 1; maxLen = r - l - 1; }\n        }\n    }\n    char* res = (char*)malloc(maxLen + 1);\n    strncpy(res, s + start, maxLen);\n    res[maxLen] = '\\0';\n    return res;\n}"
            },
        },
    },
    {
        "number": 7,
        "title": "Reverse Integer",
        "difficulty": "medium",
        "topics": ["Math"],
        "companies": ["Google", "Apple", "Bloomberg"],
        "description": "Given a signed 32-bit integer `x`, return `x` with its digits reversed. If reversing `x` causes the value to go outside the signed 32-bit integer range `[-2^31, 2^31 - 1]`, then return `0`.\n\nAssume the environment does not allow you to store 64-bit integers.",
        "constraints": "-2^31 <= x <= 2^31 - 1",
        "example_input": "x = 123",
        "example_output": "321",
        "example_explanation": "Reversing 123 gives 321.",
        "hints": "Pop the last digit and push it to the result.\nCheck for overflow before pushing.",
        "time_complexity": "O(log x)",
        "space_complexity": "O(1)",
        "test_cases": [
            {"input": "x = 123", "output": "321", "is_sample": True, "explanation": "Simple reversal"},
            {"input": "x = -123", "output": "-321", "is_sample": True, "explanation": "Negative number reversal"},
            {"input": "x = 120", "output": "21", "is_sample": True, "explanation": "Trailing zero removed"},
            {"input": "x = 1534236469", "output": "0", "is_sample": False, "explanation": "Overflow case"},
        ],
        "templates": {
            "python3": {
                "starter": "class Solution:\n    def reverse(self, x: int) -> int:\n        # Write your solution here\n        pass",
                "solution": "class Solution:\n    def reverse(self, x: int) -> int:\n        sign = -1 if x < 0 else 1\n        x = abs(x)\n        rev = 0\n        while x:\n            rev = rev * 10 + x % 10\n            x //= 10\n        rev *= sign\n        return rev if -2**31 <= rev <= 2**31 - 1 else 0"
            },
            "cpp17": {
                "starter": "class Solution {\npublic:\n    int reverse(int x) {\n        // Write your solution here\n        return 0;\n    }\n};",
                "solution": "class Solution {\npublic:\n    int reverse(int x) {\n        long rev = 0;\n        while (x != 0) {\n            rev = rev * 10 + x % 10;\n            x /= 10;\n        }\n        return (rev < INT_MIN || rev > INT_MAX) ? 0 : rev;\n    }\n};"
            },
            "java": {
                "starter": "class Solution {\n    public int reverse(int x) {\n        // Write your solution here\n        return 0;\n    }\n}",
                "solution": "class Solution {\n    public int reverse(int x) {\n        long rev = 0;\n        while (x != 0) {\n            rev = rev * 10 + x % 10;\n            x /= 10;\n        }\n        return (rev < Integer.MIN_VALUE || rev > Integer.MAX_VALUE) ? 0 : (int) rev;\n    }\n}"
            },
            "javascript": {
                "starter": "/**\n * @param {number} x\n * @return {number}\n */\nvar reverse = function(x) {\n    // Write your solution here\n};",
                "solution": "var reverse = function(x) {\n    const sign = x < 0 ? -1 : 1;\n    let rev = parseInt(Math.abs(x).toString().split('').reverse().join('')) * sign;\n    return (rev < -(2**31) || rev > 2**31 - 1) ? 0 : rev;\n};"
            },
            "c": {
                "starter": "#include <limits.h>\n\nint reverse(int x) {\n    // Write your solution here\n    return 0;\n}",
                "solution": "int reverse(int x) {\n    long rev = 0;\n    while (x != 0) {\n        rev = rev * 10 + x % 10;\n        x /= 10;\n    }\n    return (rev < INT_MIN || rev > INT_MAX) ? 0 : (int)rev;\n}"
            },
        },
    },
    {
        "number": 9,
        "title": "Palindrome Number",
        "difficulty": "easy",
        "topics": ["Math"],
        "companies": ["Amazon", "Adobe", "Apple"],
        "description": "Given an integer `x`, return `true` if `x` is a palindrome, and `false` otherwise.\n\nAn integer is a palindrome when it reads the same forward and backward.\n\nFor example, `121` is a palindrome while `123` is not.",
        "constraints": "-2^31 <= x <= 2^31 - 1",
        "example_input": "x = 121",
        "example_output": "true",
        "example_explanation": "121 reads as 121 from left to right and from right to left.",
        "hints": "Negative numbers are never palindromes.\nTry reversing only half of the number.",
        "time_complexity": "O(log n)",
        "space_complexity": "O(1)",
        "test_cases": [
            {"input": "x = 121", "output": "true", "is_sample": True, "explanation": "Reads same both ways"},
            {"input": "x = -121", "output": "false", "is_sample": True, "explanation": "Negative not palindrome"},
            {"input": "x = 10", "output": "false", "is_sample": True, "explanation": "Reads 01 from right"},
            {"input": "x = 0", "output": "true", "is_sample": False, "explanation": "0 is a palindrome"},
        ],
        "templates": {
            "python3": {
                "starter": "class Solution:\n    def isPalindrome(self, x: int) -> bool:\n        # Write your solution here\n        pass",
                "solution": "class Solution:\n    def isPalindrome(self, x: int) -> bool:\n        if x < 0:\n            return False\n        rev, orig = 0, x\n        while x > 0:\n            rev = rev * 10 + x % 10\n            x //= 10\n        return rev == orig"
            },
            "cpp17": {
                "starter": "class Solution {\npublic:\n    bool isPalindrome(int x) {\n        // Write your solution here\n        return false;\n    }\n};",
                "solution": "class Solution {\npublic:\n    bool isPalindrome(int x) {\n        if (x < 0) return false;\n        long rev = 0, orig = x;\n        while (x > 0) { rev = rev * 10 + x % 10; x /= 10; }\n        return rev == orig;\n    }\n};"
            },
            "java": {
                "starter": "class Solution {\n    public boolean isPalindrome(int x) {\n        // Write your solution here\n        return false;\n    }\n}",
                "solution": "class Solution {\n    public boolean isPalindrome(int x) {\n        if (x < 0) return false;\n        long rev = 0;\n        int orig = x;\n        while (x > 0) { rev = rev * 10 + x % 10; x /= 10; }\n        return rev == orig;\n    }\n}"
            },
            "javascript": {
                "starter": "/**\n * @param {number} x\n * @return {boolean}\n */\nvar isPalindrome = function(x) {\n    // Write your solution here\n};",
                "solution": "var isPalindrome = function(x) {\n    if (x < 0) return false;\n    let rev = 0, orig = x;\n    while (x > 0) { rev = rev * 10 + x % 10; x = Math.floor(x / 10); }\n    return rev === orig;\n};"
            },
            "c": {
                "starter": "#include <stdbool.h>\n\nbool isPalindrome(int x) {\n    // Write your solution here\n    return false;\n}",
                "solution": "bool isPalindrome(int x) {\n    if (x < 0) return false;\n    long rev = 0;\n    int orig = x;\n    while (x > 0) { rev = rev * 10 + x % 10; x /= 10; }\n    return rev == orig;\n}"
            },
        },
    },
    {
        "number": 11,
        "title": "Container With Most Water",
        "difficulty": "medium",
        "topics": ["Arrays", "Two Pointers", "Greedy"],
        "companies": ["Google", "Amazon", "Goldman Sachs"],
        "description": "You are given an integer array `height` of length `n`. There are `n` vertical lines drawn such that the two endpoints of the i-th line are `(i, 0)` and `(i, height[i])`.\n\nFind two lines that together with the x-axis form a container, such that the container contains the most water.\n\nReturn the maximum amount of water a container can store.\n\nNotice that you may not slant the container.",
        "constraints": "n == height.length\n2 <= n <= 10^5\n0 <= height[i] <= 10^4",
        "example_input": "height = [1,8,6,2,5,4,8,3,7]",
        "example_output": "49",
        "example_explanation": "The max area of water is between lines at index 1 and 8.",
        "hints": "Start with two pointers at both ends.\nMove the pointer pointing to the shorter line inward.",
        "time_complexity": "O(n)",
        "space_complexity": "O(1)",
        "test_cases": [
            {"input": "height = [1,8,6,2,5,4,8,3,7]", "output": "49", "is_sample": True, "explanation": "Between index 1 and 8"},
            {"input": "height = [1,1]", "output": "1", "is_sample": True, "explanation": "Only two lines"},
            {"input": "height = [4,3,2,1,4]", "output": "16", "is_sample": False, "explanation": "Between index 0 and 4"},
        ],
        "templates": {
            "python3": {
                "starter": "class Solution:\n    def maxArea(self, height: list[int]) -> int:\n        # Write your solution here\n        pass",
                "solution": "class Solution:\n    def maxArea(self, height: list[int]) -> int:\n        l, r = 0, len(height) - 1\n        res = 0\n        while l < r:\n            area = min(height[l], height[r]) * (r - l)\n            res = max(res, area)\n            if height[l] < height[r]:\n                l += 1\n            else:\n                r -= 1\n        return res"
            },
            "cpp17": {
                "starter": "#include <vector>\nusing namespace std;\n\nclass Solution {\npublic:\n    int maxArea(vector<int>& height) {\n        // Write your solution here\n        return 0;\n    }\n};",
                "solution": "class Solution {\npublic:\n    int maxArea(vector<int>& height) {\n        int l = 0, r = height.size() - 1, res = 0;\n        while (l < r) {\n            res = max(res, min(height[l], height[r]) * (r - l));\n            if (height[l] < height[r]) l++; else r--;\n        }\n        return res;\n    }\n};"
            },
            "java": {
                "starter": "class Solution {\n    public int maxArea(int[] height) {\n        // Write your solution here\n        return 0;\n    }\n}",
                "solution": "class Solution {\n    public int maxArea(int[] height) {\n        int l = 0, r = height.length - 1, res = 0;\n        while (l < r) {\n            res = Math.max(res, Math.min(height[l], height[r]) * (r - l));\n            if (height[l] < height[r]) l++; else r--;\n        }\n        return res;\n    }\n}"
            },
            "javascript": {
                "starter": "/**\n * @param {number[]} height\n * @return {number}\n */\nvar maxArea = function(height) {\n    // Write your solution here\n};",
                "solution": "var maxArea = function(height) {\n    let l = 0, r = height.length - 1, res = 0;\n    while (l < r) {\n        res = Math.max(res, Math.min(height[l], height[r]) * (r - l));\n        if (height[l] < height[r]) l++; else r--;\n    }\n    return res;\n};"
            },
            "c": {
                "starter": "int maxArea(int* height, int heightSize) {\n    // Write your solution here\n    return 0;\n}",
                "solution": "int maxArea(int* height, int heightSize) {\n    int l = 0, r = heightSize - 1, res = 0;\n    while (l < r) {\n        int h = height[l] < height[r] ? height[l] : height[r];\n        int area = h * (r - l);\n        if (area > res) res = area;\n        if (height[l] < height[r]) l++; else r--;\n    }\n    return res;\n}"
            },
        },
    },
    {
        "number": 13,
        "title": "Roman to Integer",
        "difficulty": "easy",
        "topics": ["Strings", "Hash Table", "Math"],
        "companies": ["Amazon", "Microsoft", "Adobe"],
        "description": "Roman numerals are represented by seven different symbols: `I`, `V`, `X`, `L`, `C`, `D` and `M`.\n\nGiven a roman numeral, convert it to an integer.",
        "constraints": "1 <= s.length <= 15\ns contains only the characters ('I', 'V', 'X', 'L', 'C', 'D', 'M').\nIt is guaranteed that s is a valid roman numeral in the range [1, 3999].",
        "example_input": 's = "III"',
        "example_output": "3",
        "example_explanation": "III = 3.",
        "hints": "If a smaller value appears before a larger value, subtract it.\nOtherwise, add it.",
        "time_complexity": "O(n)",
        "space_complexity": "O(1)",
        "test_cases": [
            {"input": 's = "III"', "output": "3", "is_sample": True, "explanation": "I + I + I = 3"},
            {"input": 's = "LVIII"', "output": "58", "is_sample": True, "explanation": "L=50, V=5, III=3"},
            {"input": 's = "MCMXCIV"', "output": "1994", "is_sample": True, "explanation": "M=1000, CM=900, XC=90, IV=4"},
        ],
        "templates": {
            "python3": {
                "starter": "class Solution:\n    def romanToInt(self, s: str) -> int:\n        # Write your solution here\n        pass",
                "solution": "class Solution:\n    def romanToInt(self, s: str) -> int:\n        m = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000}\n        res = 0\n        for i in range(len(s)):\n            if i + 1 < len(s) and m[s[i]] < m[s[i+1]]:\n                res -= m[s[i]]\n            else:\n                res += m[s[i]]\n        return res"
            },
            "cpp17": {
                "starter": "#include <string>\nusing namespace std;\n\nclass Solution {\npublic:\n    int romanToInt(string s) {\n        // Write your solution here\n        return 0;\n    }\n};",
                "solution": "class Solution {\npublic:\n    int romanToInt(string s) {\n        unordered_map<char,int> m = {{'I',1},{'V',5},{'X',10},{'L',50},{'C',100},{'D',500},{'M',1000}};\n        int res = 0;\n        for (int i = 0; i < s.size(); i++) {\n            if (i+1 < s.size() && m[s[i]] < m[s[i+1]]) res -= m[s[i]];\n            else res += m[s[i]];\n        }\n        return res;\n    }\n};"
            },
            "java": {
                "starter": "class Solution {\n    public int romanToInt(String s) {\n        // Write your solution here\n        return 0;\n    }\n}",
                "solution": "class Solution {\n    public int romanToInt(String s) {\n        Map<Character,Integer> m = Map.of('I',1,'V',5,'X',10,'L',50,'C',100,'D',500,'M',1000);\n        int res = 0;\n        for (int i = 0; i < s.length(); i++) {\n            if (i+1 < s.length() && m.get(s.charAt(i)) < m.get(s.charAt(i+1))) res -= m.get(s.charAt(i));\n            else res += m.get(s.charAt(i));\n        }\n        return res;\n    }\n}"
            },
            "javascript": {
                "starter": "/**\n * @param {string} s\n * @return {number}\n */\nvar romanToInt = function(s) {\n    // Write your solution here\n};",
                "solution": "var romanToInt = function(s) {\n    const m = {'I':1,'V':5,'X':10,'L':50,'C':100,'D':500,'M':1000};\n    let res = 0;\n    for (let i = 0; i < s.length; i++) {\n        if (i+1 < s.length && m[s[i]] < m[s[i+1]]) res -= m[s[i]];\n        else res += m[s[i]];\n    }\n    return res;\n};"
            },
            "c": {
                "starter": "int romanToInt(char* s) {\n    // Write your solution here\n    return 0;\n}",
                "solution": "int val(char c) {\n    switch(c) {\n        case 'I': return 1; case 'V': return 5; case 'X': return 10;\n        case 'L': return 50; case 'C': return 100; case 'D': return 500;\n        case 'M': return 1000; default: return 0;\n    }\n}\nint romanToInt(char* s) {\n    int res = 0;\n    for (int i = 0; s[i]; i++) {\n        if (s[i+1] && val(s[i]) < val(s[i+1])) res -= val(s[i]);\n        else res += val(s[i]);\n    }\n    return res;\n}"
            },
        },
    },
    {
        "number": 14,
        "title": "Longest Common Prefix",
        "difficulty": "easy",
        "topics": ["Strings"],
        "companies": ["Google", "Amazon", "Adobe"],
        "description": "Write a function to find the longest common prefix string amongst an array of strings.\n\nIf there is no common prefix, return an empty string `\"\"`.",
        "constraints": "1 <= strs.length <= 200\n0 <= strs[i].length <= 200\nstrs[i] consists of only lowercase English letters.",
        "example_input": 'strs = ["flower","flow","flight"]',
        "example_output": '"fl"',
        "example_explanation": '"fl" is the longest common prefix.',
        "hints": "Compare characters at each position across all strings.\nStop when characters differ or a string ends.",
        "time_complexity": "O(S)",
        "space_complexity": "O(1)",
        "test_cases": [
            {"input": 'strs = ["flower","flow","flight"]', "output": '"fl"', "is_sample": True, "explanation": "Common prefix is 'fl'"},
            {"input": 'strs = ["dog","racecar","car"]', "output": '""', "is_sample": True, "explanation": "No common prefix"},
            {"input": 'strs = ["interspecies","interstellar","interstate"]', "output": '"inters"', "is_sample": False, "explanation": "Common prefix is 'inters'"},
        ],
        "templates": {
            "python3": {
                "starter": "class Solution:\n    def longestCommonPrefix(self, strs: list[str]) -> str:\n        # Write your solution here\n        pass",
                "solution": "class Solution:\n    def longestCommonPrefix(self, strs: list[str]) -> str:\n        if not strs:\n            return ''\n        for i in range(len(strs[0])):\n            for s in strs[1:]:\n                if i >= len(s) or s[i] != strs[0][i]:\n                    return strs[0][:i]\n        return strs[0]"
            },
            "cpp17": {
                "starter": "#include <vector>\n#include <string>\nusing namespace std;\n\nclass Solution {\npublic:\n    string longestCommonPrefix(vector<string>& strs) {\n        // Write your solution here\n        return \"\";\n    }\n};",
                "solution": "class Solution {\npublic:\n    string longestCommonPrefix(vector<string>& strs) {\n        if (strs.empty()) return \"\";\n        for (int i = 0; i < strs[0].size(); i++) {\n            for (int j = 1; j < strs.size(); j++) {\n                if (i >= strs[j].size() || strs[j][i] != strs[0][i])\n                    return strs[0].substr(0, i);\n            }\n        }\n        return strs[0];\n    }\n};"
            },
            "java": {
                "starter": "class Solution {\n    public String longestCommonPrefix(String[] strs) {\n        // Write your solution here\n        return \"\";\n    }\n}",
                "solution": "class Solution {\n    public String longestCommonPrefix(String[] strs) {\n        if (strs.length == 0) return \"\";\n        for (int i = 0; i < strs[0].length(); i++) {\n            for (int j = 1; j < strs.length; j++) {\n                if (i >= strs[j].length() || strs[j].charAt(i) != strs[0].charAt(i))\n                    return strs[0].substring(0, i);\n            }\n        }\n        return strs[0];\n    }\n}"
            },
            "javascript": {
                "starter": "/**\n * @param {string[]} strs\n * @return {string}\n */\nvar longestCommonPrefix = function(strs) {\n    // Write your solution here\n};",
                "solution": "var longestCommonPrefix = function(strs) {\n    if (!strs.length) return '';\n    for (let i = 0; i < strs[0].length; i++) {\n        for (let j = 1; j < strs.length; j++) {\n            if (i >= strs[j].length || strs[j][i] !== strs[0][i])\n                return strs[0].substring(0, i);\n        }\n    }\n    return strs[0];\n};"
            },
            "c": {
                "starter": "#include <string.h>\n\nchar* longestCommonPrefix(char** strs, int strsSize) {\n    // Write your solution here\n    return \"\";\n}",
                "solution": "char* longestCommonPrefix(char** strs, int strsSize) {\n    if (strsSize == 0) return \"\";\n    for (int i = 0; strs[0][i]; i++) {\n        for (int j = 1; j < strsSize; j++) {\n            if (!strs[j][i] || strs[j][i] != strs[0][i]) {\n                strs[0][i] = '\\0';\n                return strs[0];\n            }\n        }\n    }\n    return strs[0];\n}"
            },
        },
    },
]
