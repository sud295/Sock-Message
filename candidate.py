import random
class Candidate():
    def __init__(self) -> None:
        self.votes = 0
        self.rank = [random.randint(0, 1000) for i in range(100)]
        self.term = 0

    def vote(self, candidate: 'Candidate') -> bool:
        for i in range(100):
            if candidate.rank[i] > self.rank[i]:
                return True
            elif candidate.rank[i] < self.rank[i]:
                return False
        return True
    
    def outcome(self, num_participants: int) -> bool:
        if self.votes > num_participants//2:
            return True
        return False
