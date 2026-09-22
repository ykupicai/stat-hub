# -*- coding: utf-8 -*-
"""重製圖3-1（溫度及降雨量月平均統計圖）、圖3-3（平均日照時數統計圖），統計期間 2016-2025"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
plt.rcParams['font.sans-serif']=['Microsoft JhengHei']
plt.rcParams['axes.unicode_minus']=False

d=json.load(open("new_table31.json",encoding="utf-8"))["2016-2025"]
mon=[f"{m}月" for m in range(1,13)]
tmax,tmean,tmin,rain,sun = d['tmax'],d['tmean'],d['tmin'],d['rain'],d['sun']
def r0(v):  # 一般四捨五入（非銀行家）
    from decimal import Decimal, ROUND_HALF_UP
    return int(Decimal(str(v)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

# ---------- 圖3-1 ----------
fig,ax=plt.subplots(figsize=(9.44,5.98),dpi=150)
ax2=ax.twinx()
ax2.bar(mon,rain,color="#4FC3F7",width=0.55,zorder=2,label="降水量(mm)")
ax.plot(mon,tmax,color="#E8191B",marker="s",ms=5,lw=2,zorder=4,label="最高溫度(°C)")
ax.plot(mon,tmean,color="#F5B800",marker="s",ms=5,lw=2,zorder=4,label="平均溫度(°C)")
ax.plot(mon,tmin,color="#4A7B2A",marker="s",ms=5,lw=2,zorder=4,label="最低溫度(°C)")
ax.set_ylim(0,40); ax.yaxis.set_major_locator(MultipleLocator(5))
ax2.set_ylim(0,800); ax2.yaxis.set_major_locator(MultipleLocator(100))
ax.set_ylabel("溫度(℃)",fontsize=11); ax2.set_ylabel("降水量(mm)",fontsize=11)
ax.set_zorder(ax2.get_zorder()+1); ax.patch.set_visible(False)
ax.grid(axis='y',color="#D9D9D9",lw=.8,zorder=0)
for i,v in enumerate(tmax): ax.annotate(f"{r0(v)}",(i,v),textcoords="offset points",xytext=(0,9),ha="center",fontsize=10.5,fontweight="bold",color="#404040")
for i,v in enumerate(tmean): ax.annotate(f"{r0(v)}",(i,v),textcoords="offset points",xytext=(0,9),ha="center",fontsize=10.5,fontweight="bold",color="#404040")
for i,v in enumerate(tmin): ax.annotate(f"{r0(v)}",(i,v),textcoords="offset points",xytext=(0,9),ha="center",fontsize=10.5,fontweight="bold",color="#404040")
for i,v in enumerate(rain): ax2.annotate(f"{r0(v)}",(i,v),textcoords="offset points",xytext=(0,6),ha="center",fontsize=10.5,fontweight="bold",color="#404040",zorder=6)
ax.tick_params(labelsize=11); ax2.tick_params(labelsize=11)
for lb in ax.get_xticklabels(): lb.set_fontweight("bold")
h1,l1=ax.get_legend_handles_labels(); h2,l2=ax2.get_legend_handles_labels()
ax.legend(h2+h1,l2+l1,loc="upper center",bbox_to_anchor=(0.5,-0.10),ncol=4,frameon=False,fontsize=11)
for s in ax.spines.values(): s.set_color("#BFBFBF")
fig.tight_layout(rect=(0,0,0.985,1)); fig.savefig("new_fig3-1.png",dpi=150,facecolor="white")
plt.close(fig)

# ---------- 圖3-3 ----------
fig,ax=plt.subplots(figsize=(6.77,3.17),dpi=330)
ax.bar(mon,sun,color="#C8804B",width=0.45,zorder=2)
ax.set_ylim(0,250); ax.yaxis.set_major_locator(MultipleLocator(50))
ax.set_ylabel("日照時數(小時)",fontsize=11)
ax.grid(axis='y',color="#D9D9D9",lw=.8,zorder=0)
for i,v in enumerate(sun):
    ax.annotate(f"{v:g}",(i,v),textcoords="offset points",xytext=(0,5),ha="center",fontsize=10.5,fontweight="bold",color="#262626")
ax.tick_params(labelsize=11)
for lb in ax.get_xticklabels(): lb.set_fontweight("bold")
for sname in ("top","right","left","bottom"): ax.spines[sname].set_color("#BFBFBF")
fig.tight_layout(); fig.savefig("new_fig3-3.png",dpi=330,facecolor="white")
plt.close(fig)
print("圖3-1 標註 最高", [r0(v) for v in tmax])
print("圖3-1 標註 平均", [r0(v) for v in tmean])
print("圖3-1 標註 最低", [r0(v) for v in tmin])
print("圖3-1 標註 降水", [r0(v) for v in rain])
print("圖3-3 日照", sun)
