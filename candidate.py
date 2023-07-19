import random
class Candidate():
    def __init__(self) -> None:
        self.votes = 0
        self.rank = [random.randint(0, 1000) for i in range(100)]
        self.term = 0
    
    def compare_rank(self, other_rank: list) -> bool:
        for i in range(100):
            if other_rank[i] > self.rank[i]:
                return True
            elif other_rank[i] < self.rank[i]:
                return False
        return True
    
