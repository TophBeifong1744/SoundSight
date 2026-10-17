"""Python整数参考：独立逐样本计算均值、Hann和RNE，不调用RTL函数。"""
from pathlib import Path
import random
P=Path(__file__).resolve().parents[2]
T=P/'simulation/tb/stm32'
rand=random.Random(20261017)
samples=[[rand.randrange(-8388608,8388608) for _ in range(4)] for _ in range(1024)]
samples[0]=[-8388608,8388607,-1,1]
samples[1]=[8388607,-8388608,1,-1]
def rne(n,k):
    q,r=divmod(n,1<<k)
    return q+int(r>(1<<(k-1)) or (r==(1<<(k-1)) and q%2!=0))
means=[rne(sum(row[ch] for row in samples),10) for ch in range(4)]
hann=[int(x,16) for x in (P/'project/rtl/hann-u18f17.mem').read_text().split()]
assert len(hann)==1024
raw=[''.join(f'{v&0xffffff:06x}' for v in reversed(row)) for row in samples]
(T/'pcm_vectors.mem').write_text('\n'.join(raw)+'\n')
gold=[]
for domain in range(2):
    for channel in range(4):
        for i,row in enumerate(samples):
            operand=row[channel]-(means[channel] if domain==0 else 0)
            value=rne(operand*hann[i],17)
            assert -(1<<(23 if domain else 24))<=value<(1<<(23 if domain else 24))
            gold.append(f'{(value*16)&0x1fffffff:08x}')
(T/'preprocess_gold.mem').write_text('\n'.join(gold)+'\n')
print('PREPROCESS_VECTORS_READY points=',len(gold),'means=',means)
