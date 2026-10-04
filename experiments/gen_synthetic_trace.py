import os, pickle, random, sys

# adjust this path if your folder structure differs
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sim-upstream", "code", "split"))
from LambdaData import LambdaData

random.seed(42)
num_funcs = 20          # enough diversity to see policy differences
out_dir = os.path.join(os.path.dirname(__file__), "traces")
os.makedirs(out_dir, exist_ok=True)

lambdas = {}
trace = []

sim_duration_ms = 1 * 60 * 60 * 1000  # 4 hours of simulated traffic

for i in range(num_funcs):
    name = f"func_{i}"
    # mem sizes spanning realistic range (MB), matching paper's Table 1 ballpark
    mem = random.choice([64, 128, 256, 512, 1024])
    cold_time = random.uniform(0.3, 5.0)
    warm_time = cold_time * random.uniform(0.05, 0.3)
    d = LambdaData(name, mem, cold_time, warm_time)
    lambdas[name] = (name, mem, cold_time, warm_time)

    # heavy-tailed invocation frequency: a few hot functions, many cold ones
    freq_ms = random.choice([200, 500, 2000, 2000, 10000, 10000, 60000, 60000, 300000])
    t = random.randint(0, 5000)
    while t < sim_duration_ms:
        trace.append((d, t))
        t += freq_ms + random.randint(-50, 50)

trace = sorted(trace, key=lambda x: x[1])
save_pth = os.path.join(out_dir, f"{num_funcs}-b.pckl")
with open(save_pth, "w+b") as f:
    pickle.dump((lambdas, trace), f)

print(f"Wrote {len(trace)} invocations across {num_funcs} functions to {save_pth}")