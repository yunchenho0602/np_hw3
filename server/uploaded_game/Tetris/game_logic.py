import random
from constants import GRID_W, GRID_H

SHAPES = [
    [[1,1,1,1]],
    [[2,2],[2,2]],
    [[0,3,0],[3,3,3]],
    [[4,0,0],[4,4,4]],
    [[0,0,5],[5,5,5]],
    [[0,6,6],[6,6,0]],
    [[7,7,0],[0,7,7]],
]

class TetrisGame:
    def __init__(self):
        self.grid = [[0]*GRID_W for _ in range(GRID_H)]
        self.new_piece()
        self.dead = False

    def new_piece(self):
        self.shape = random.choice(SHAPES)
        self.x = GRID_W//2 - len(self.shape[0])//2
        self.y = 0
        if not self.valid():
            self.dead = True

    def valid(self, dx=0, dy=0, shape=None):
        shape = shape or self.shape
        for y,row in enumerate(shape):
            for x,val in enumerate(row):
                if val:
                    nx, ny = self.x+x+dx, self.y+y+dy
                    if nx<0 or nx>=GRID_W or ny>=GRID_H:
                        return False
                    if ny>=0 and self.grid[ny][nx]:
                        return False
        return True

    def rotate(self):
        rotated = list(zip(*self.shape[::-1]))
        if self.valid(shape=rotated):
            self.shape = rotated

    def lock(self):
        for y,row in enumerate(self.shape):
            for x,val in enumerate(row):
                if val and self.y+y>=0:
                    self.grid[self.y+y][self.x+x] = val
        return self.clear_lines()

    def clear_lines(self):
        cleared = 0
        new = []
        for r in self.grid:
            if all(r):
                cleared += 1
            else:
                new.append(r)
        while len(new)<GRID_H:
            new.insert(0,[0]*GRID_W)
        self.grid = new
        return cleared

    def add_garbage(self,n):
        for _ in range(n):
            self.grid.pop(0)
            hole=random.randint(0,GRID_W-1)
            row=[8]*GRID_W
            row[hole]=0
            self.grid.append(row)

    def tick(self):
        if self.valid(dy=1):
            self.y+=1
            return 0
        lines=self.lock()
        self.new_piece()
        return lines

    def serialize(self):
        g=[r[:] for r in self.grid]
        for y,row in enumerate(self.shape):
            for x,val in enumerate(row):
                if val and self.y+y>=0:
                    g[self.y+y][self.x+x]=val
        return {"grid":g,"dead":self.dead}
