import datetime
import gc
import lightgbm
import numpy
import pandas
import pickle
import random
import requests
import sklearn
import sklearn.metrics
import time
import torch
import transformers
import warnings
import zipfile
pandas.set_option("max.columns", 32)
pandas.set_option("max.rows", 256)
warnings.filterwarnings("ignore")

句長 = 32


def 整理名稱(某表, 前綴=""):
	某表.columns = 前綴 + 某表.columns.get_level_values(0) + "_" + 某表.columns.get_level_values(1)
	return 某表
pandas.DataFrame.整理名稱 = 整理名稱

def 統計特征(某表, 鍵, 列, 統計函式, 前綴=""):
	return 某表.groupby(鍵).aggregate({子: 統計函式 for 子 in 列}).整理名稱(前綴).reset_index()
pandas.DataFrame.統計特征 = 統計特征

def 統計標準特征(某表, 鍵, 前綴=None):
	if not isinstance(鍵, list):
		鍵 = [鍵]
	if 前綴 is None:
		前綴 = "".join(鍵)
	某特征表 = 某表.groupby(鍵).aggregate({"標籤": ["count", "sum"]}).reset_index()
	某特征表.columns = 鍵 + ["%s樣本數" % 前綴, "%s正樣本數" % 前綴]
	某特征表["%s正樣本率" % 前綴] = (1 + 某特征表["%s正樣本數" % 前綴]) / (2 + 某特征表["%s樣本數" % 前綴])
	return 某特征表
pandas.DataFrame.統計標準特征 = 統計標準特征

def 統計測試特征(某値, 統計函式):
	if len(某値) == 0:
		return len(統計函式) * [numpy.nan]

	結果 = []
	for 甲函式 in 統計函式:
		if 甲函式 == "sum":
			結果 += [sum(某値)]
		elif 甲函式 == "mean":
			結果 += [sum(某値) / len(某値)]
		elif 甲函式 == "min":
			結果 += [min(某値)]
		elif 甲函式 == "max":
			結果 += [max(某値)]
		else:
			raise Exception("非法函式！")

	return 結果


def 取得最長公共子序列長(甲串, 乙串):
	結果 = [[0 for _ in range(1 + len(甲串))] for __ in range(1 + len(乙串))]
	for 甲 in range(1, 1 + len(乙串)):
		for 乙 in range(1, 1 + len(甲串)):
			if 乙串[甲 - 1] == 甲串[乙 - 1]:
				結果[甲][乙] = 1 + 結果[甲 - 1][乙 - 1]
			else:
				結果[甲][乙] = max(結果[甲 - 1][乙], 結果[甲][乙 - 1])
	return 結果[-1][-1]

def 取得最長公共子串長(甲串, 乙串):
	結果 = [[0 for _ in range(1 + len(甲串))] for __ in range(1 + len(乙串))]
	結果長度 = 0
	for 甲 in range(1, 1 + len(乙串)):
		for 乙 in range(1, 1 + len(甲串)):
			if 乙串[甲 - 1] == 甲串[乙 - 1]:
				結果[甲][乙] = 1 + 結果[甲 - 1][乙 - 1]
				結果長度 = max(結果長度, 結果[甲][乙])
	return 結果長度

def 取得編輯距離(甲串, 乙串):
	距離矩陣 = [[子 + 丑 for 子 in range(len(乙串) + 1)] for 丑 in range(len(甲串) + 1)]

	for 甲 in range(1, len(甲串) + 1):
		for 乙 in range(1, len(乙串) + 1):
			if 甲串[甲 - 1] == 乙串[乙 - 1]:
				距離 = 0
			else:
				距離 = 1
			距離矩陣[甲][乙] = min(距離矩陣[甲 - 1][乙] + 1, 距離矩陣[甲][乙 - 1] + 1, 距離矩陣[甲 - 1][乙 - 1] + 距離)

	return 距離矩陣[len(甲串)][len(乙串)]

def 取得預處理列(某列, 某詞字典):
	上句 = [str(某詞字典.get(子, 1)) for 子 in 某列.上句字串.split(" ")]
	下句 = [str(某詞字典.get(子, 1)) for 子 in 某列.下句字串.split(" ")]

	上句詞數 = len(上句)
	下句詞數 = len(下句)

	上下首詞 = 上句[0] + "_" + 下句[0]
	上下末詞 = 上句[-1] + "_" + 下句[-1]

	上句集 = set(上句)
	下句集 = set(下句)

	上異句 = []
	上同句 = []
	上雙詞句 = []
	上三詞句 = []
	for 甲, 甲詞 in enumerate(上句):
		if 上句[甲] not in 下句集:
			上異句 += [甲詞]
		else:
			上同句 += [甲詞]
		if 甲 < len(上句) - 1:
			上雙詞句 += ["%s_%s" % (甲詞, 上句[1 + 甲])]
			if 甲 < len(上句) - 2:
				上三詞句 += ["%s_%s_%s" % (甲詞, 上句[1 + 甲], 上句[2 + 甲])]

	下異句 = []
	下同句 = []
	下雙詞句 = []
	下三詞句 = []
	for 甲, 甲詞 in enumerate(下句):
		if 下句[甲] not in 上句集:
			下異句 += [甲詞]
		else:
			下同句 += [甲詞]
		if 甲 < len(下句) - 1:
			下雙詞句 += ["%s_%s" % (甲詞, 下句[1 + 甲])]
			if 甲 < len(下句) - 2:
				下三詞句 += ["%s_%s_%s" % (甲詞, 下句[1 + 甲], 下句[2 + 甲])]

	上句首雙詞 = "0"
	下句首雙詞 = "0"
	上句末雙詞 = "0"
	下句末雙詞 = "0"
	if len(上雙詞句) > 0:
		上句首雙詞 = 上雙詞句[0]
		上句末雙詞 = 上雙詞句[-1]
	if len(下雙詞句) > 0:
		下句首雙詞 = 下雙詞句[0]
		下句末雙詞 = 下雙詞句[-1]
	上下首雙詞 = 上句首雙詞 + "_" + 上句末雙詞
	上下末雙詞 = 下句首雙詞 + "_" + 下句末雙詞


	上異句字串 = " ".join(上異句)
	下異句字串 = " ".join(下異句)
	上異句詞數 = len(上異句)
	下異句詞數 = len(下異句)

	上同句字串 = " ".join(上同句)
	下同句字串 = " ".join(下同句)
	上同句詞數 = len(上同句)
	下同句詞數 = len(下同句)

	上異句首詞 = "0"
	下異句首詞 = "0"
	上異句末詞 = "0"
	下異句末詞 = "0"
	if len(上異句) > 0:
		上異句首詞 = 上異句[0]
		上異句末詞 = 上異句[-1]
	if len(下異句) > 0:
		下異句首詞 = 下異句[0]
		下異句末詞 = 下異句[-1]
	上下異句首詞 = 上異句首詞 + "_" + 下異句首詞
	上下異句末詞 = 上異句末詞 + "_" + 下異句末詞

	上雙詞句集 = set(上雙詞句)
	下雙詞句集 = set(下雙詞句)
	上三詞句集 = set(上三詞句)
	下三詞句集 = set(下三詞句)
	上雙詞異句 = []
	下雙詞異句 = []
	上三詞異句 = []
	下三詞異句 = []
	for 甲, 甲詞 in enumerate(上雙詞句):
		if 上雙詞句[甲] not in 下雙詞句集:
			上雙詞異句 += [甲詞]
	for 甲, 甲詞 in enumerate(下雙詞句):
		if 下雙詞句[甲] not in 上雙詞句集:
			下雙詞異句 += [甲詞]
	for 甲, 甲詞 in enumerate(上三詞句):
		if 上三詞句[甲] not in 下三詞句集:
			上三詞異句 += [甲詞]
	for 甲, 甲詞 in enumerate(下三詞句):
		if 下三詞句[甲] not in 上三詞句集:
			下三詞異句 += [甲詞]

	上異句首雙詞 = "0"
	下異句首雙詞 = "0"
	上異句末雙詞 = "0"
	下異句末雙詞 = "0"
	if len(上雙詞異句) > 0:
		上異句首雙詞 = 上雙詞異句[0]
		上異句末雙詞 = 上雙詞異句[-1]
	if len(下雙詞異句) > 0:
		下異句首雙詞 = 下雙詞異句[0]
		下異句末雙詞 = 下雙詞異句[-1]
	上下異句首雙詞 = 上異句首雙詞 + "_" + 上異句末雙詞
	上下異句末雙詞 = 下異句首雙詞 + "_" + 下異句末雙詞

	上下交集 = 上句集.intersection(下句集)
	上下並集 = 上句集.union(下句集)
	上差集 = 上句集.difference(下句集)
	下差集 = 下句集.difference(上句集)

	交集詞數 = len(上下交集)
	並集詞數 = len(上下並集)
	差集詞數和 = len(上差集) + len(下差集)
	差集詞數積 = len(上差集) * len(下差集)

	for 甲 in range(min(len(上句), len(下句))):
		if 上句[甲] != 下句[甲]:
			break
	公共前綴長 = 甲
	for 甲 in range(min(len(上句), len(下句))):
		if 上句[-1 - 甲] != 下句[-1 - 甲]:
			break
	公共後綴長 = 甲

	最長公共子序列長 = 取得最長公共子序列長(上句, 下句)
	最長公共子串長 = 取得最長公共子串長(上句, 下句)
	編輯距離 = 取得編輯距離(上句, 下句)

	return [
		上句, 下句, 上句詞數, 下句詞數
		, 上下首詞, 上下末詞
		, 上異句字串, 下異句字串, 上異句, 下異句, 上異句詞數, 下異句詞數
		, 上異句首詞, 下異句首詞, 上下異句首詞, 上異句末詞, 下異句末詞, 上下異句末詞
		, 上同句字串, 下同句字串, 上同句, 下同句, 上同句詞數, 下同句詞數
		, 上雙詞句, 下雙詞句, 上雙詞異句, 下雙詞異句
		, 上下首雙詞, 上下末雙詞, 上下異句首雙詞, 上下異句末雙詞
		, 上三詞句, 下三詞句, 上三詞異句, 下三詞異句
		, 交集詞數, 並集詞數, 差集詞數和, 差集詞數積
		, 公共前綴長, 公共後綴長, 最長公共子序列長, 最長公共子串長, 編輯距離
	]

def 取得測試預處理列(某上句字串, 某下句字串, 某詞字典):
	上句 = [str(某詞字典.get(子, 1)) for 子 in 某上句字串.split(" ")]
	下句 = [str(某詞字典.get(子, 1)) for 子 in 某下句字串.split(" ")]

	上句詞數 = len(上句)
	下句詞數 = len(下句)

	上下首詞 = 上句[0] + "_" + 下句[0]
	上下末詞 = 上句[-1] + "_" + 下句[-1]

	上句集 = set(上句)
	下句集 = set(下句)

	上異句 = []
	上同句 = []
	上雙詞句 = []
	上三詞句 = []
	for 甲, 甲詞 in enumerate(上句):
		if 上句[甲] not in 下句集:
			上異句 += [甲詞]
		else:
			上同句 += [甲詞]
		if 甲 < len(上句) - 1:
			上雙詞句 += ["%s_%s" % (甲詞, 上句[1 + 甲])]
			if 甲 < len(上句) - 2:
				上三詞句 += ["%s_%s_%s" % (甲詞, 上句[1 + 甲], 上句[2 + 甲])]

	下異句 = []
	下同句 = []
	下雙詞句 = []
	下三詞句 = []
	for 甲, 甲詞 in enumerate(下句):
		if 下句[甲] not in 上句集:
			下異句 += [甲詞]
		else:
			下同句 += [甲詞]
		if 甲 < len(下句) - 1:
			下雙詞句 += ["%s_%s" % (甲詞, 下句[1 + 甲])]
			if 甲 < len(下句) - 2:
				下三詞句 += ["%s_%s_%s" % (甲詞, 下句[1 + 甲], 下句[2 + 甲])]

	上異句字串 = " ".join(上異句)
	下異句字串 = " ".join(下異句)

	上異句首詞 = "0"
	下異句首詞 = "0"
	上異句末詞 = "0"
	下異句末詞 = "0"
	if len(上異句) > 0:
		上異句首詞 = 上異句[0]
		上異句末詞 = 上異句[-1]
	if len(下異句) > 0:
		下異句首詞 = 下異句[0]
		下異句末詞 = 下異句[-1]
	上下異句首詞 = 上異句首詞 + "_" + 下異句首詞
	上下異句末詞 = 上異句末詞 + "_" + 下異句末詞

	上雙詞句集 = set(上雙詞句)
	下雙詞句集 = set(下雙詞句)
	上三詞句集 = set(上三詞句)
	下三詞句集 = set(下三詞句)
	上雙詞異句 = []
	下雙詞異句 = []
	上三詞異句 = []
	下三詞異句 = []
	for 甲, 甲詞 in enumerate(上雙詞句):
		if 上雙詞句[甲] not in 下雙詞句集:
			上雙詞異句 += [甲詞]
	for 甲, 甲詞 in enumerate(下雙詞句):
		if 下雙詞句[甲] not in 上雙詞句集:
			下雙詞異句 += [甲詞]
	for 甲, 甲詞 in enumerate(上三詞句):
		if 上三詞句[甲] not in 下三詞句集:
			上三詞異句 += [甲詞]
	for 甲, 甲詞 in enumerate(下三詞句):
		if 下三詞句[甲] not in 上三詞句集:
			下三詞異句 += [甲詞]

	上下交集 = 上句集.intersection(下句集)
	上下並集 = 上句集.union(下句集)
	上差集 = 上句集.difference(下句集)
	下差集 = 下句集.difference(上句集)

	交集詞數 = len(上下交集)
	並集詞數 = len(上下並集)
	差集詞數和 = len(上差集) + len(下差集)
	差集詞數積 = len(上差集) * len(下差集)

	for 甲 in range(min(len(上句), len(下句))):
		if 上句[甲] != 下句[甲]:
			break
	公共前綴長 = 甲
	for 甲 in range(min(len(上句), len(下句))):
		if 上句[-1 - 甲] != 下句[-1 - 甲]:
			break
	公共後綴長 = 甲

	最長公共子序列長 = 取得最長公共子序列長(上句, 下句)
	最長公共子串長 = 取得最長公共子串長(上句, 下句)
	編輯距離 = 取得編輯距離(上句, 下句)

	return [
		上句, 下句, 上句詞數, 下句詞數
		, 上下首詞, 上下末詞
		, 上異句字串, 下異句字串, 上異句, 下異句
		, 上下異句首詞, 上下異句末詞
		, 上雙詞異句, 下雙詞異句, 上三詞異句, 下三詞異句
		, 交集詞數, 並集詞數, 差集詞數和, 差集詞數積
		, 公共前綴長, 公共後綴長, 最長公共子序列長, 最長公共子串長, 編輯距離
	]

def 預處理(某表, 某詞字典):
	某表[[
		"上句", "下句", "上句詞數", "下句詞數"
		, "上下首詞", "上下末詞"
		, "上異句字串", "下異句字串", "上異句", "下異句", "上異句詞數", "下異句詞數"
		, "上異句首詞", "下異句首詞", "上下異句首詞", "上異句末詞", "下異句末詞", "上下異句末詞"
		, "上同句字串", "下同句字串", "上同句", "下同句", "上同句詞數", "下同句詞數"
		, "上雙詞句", "下雙詞句", "上雙詞異句", "下雙詞異句"
		, "上下首雙詞", "上下末雙詞", "上下異句首雙詞", "上下異句末雙詞"
		, "上三詞句", "下三詞句", "上三詞異句", "下三詞異句"
		, "交集詞數", "並集詞數", "差集詞數和", "差集詞數積"
		, "公共前綴長", "公共後綴長", "最長公共子序列長", "最長公共子串長", "編輯距離"
	]] = 某表.apply(lambda 子列: pandas.Series(取得預處理列(子列, 某詞字典=某詞字典)), axis=1)

	return 某表



訓練表 = pandas.concat([
	pandas.read_csv("gaiic_track3_round1_train_20210228.tsv", header=None, names=["上句字串", "下句字串", "標籤"], sep="\t")
	, pandas.read_csv("gaiic_track3_round2_train_20210407.tsv", header=None, names=["上句字串", "下句字串", "標籤"], sep="\t")
], ignore_index=True)
訓練表 = pandas.concat([訓練表, 訓練表.rename({"上句字串": "下句字串", "下句字串": "上句字串"}, axis=1)], ignore_index=True)
訓練表 = 訓練表.loc[訓練表.上句字串 < 訓練表.下句字串].reset_index(drop=True)
訓練表 = 訓練表.groupby(["上句字串", "下句字串"]).aggregate({"標籤": "min"}).reset_index()
訓練表["標識"] = range(-1, -1 - len(訓練表), -1)

測試表 = pandas.concat([
	pandas.read_csv("gaiic_track3_round1_testA_20210228.tsv", header=None, names=["上句字串", "下句字串"], sep="\t")
	, pandas.read_csv("gaiic_track3_round1_testB_20210317.tsv", header=None, names=["上句字串", "下句字串"], sep="\t")
], ignore_index=True)
測試表 = pandas.concat([測試表, 測試表.rename({"上句字串": "下句字串", "下句字串": "上句字串"}, axis=1)], ignore_index=True)
測試表 = 測試表.loc[測試表.上句字串 < 測試表.下句字串].reset_index(drop=True)
測試表 = 測試表.drop_duplicates(["上句字串", "下句字串"], ignore_index=True)
測試表 = 測試表.merge(訓練表.loc[:, ["上句字串", "下句字串", "標識"]], on=["上句字串", "下句字串"], how="left")
測試表 = 測試表.loc[測試表.標識.isna()].reset_index(drop=True)
測試表["標識"] = range(len(測試表))
測試表["標籤"] = -1


詞表 = pandas.concat([
	訓練表.loc[:, ["標識", "上句字串"]].rename({"上句字串": "句字串"}, axis=1).assign(上下句 = 0)
	, 訓練表.loc[:, ["標識", "下句字串"]].rename({"下句字串": "句字串"}, axis=1).assign(上下句 = 1)
	, 測試表.loc[:, ["標識", "上句字串"]].rename({"上句字串": "句字串"}, axis=1).assign(上下句 = 0)
	, 測試表.loc[:, ["標識", "下句字串"]].rename({"下句字串": "句字串"}, axis=1).assign(上下句 = 1)
])
詞表 = 詞表.loc[:, ["標識", "上下句", "句字串"]].set_index(["標識", "上下句"]).句字串.str.split().apply(pandas.Series).stack().reset_index()
詞表.columns = ["標識", "上下句", "詞序號", "詞"]
詞表 = 詞表.groupby("詞").aggregate({"標識": "count"}).reset_index().rename({"標識": "詞頻"}, axis=1)
詞表 = 詞表.loc[詞表.詞頻 >= 3].sort_values(["詞頻", "詞"], ignore_index=True, ascending=False)
詞表["新詞"] = [5 + 子 for 子 in range(len(詞表))]
詞字典 = 詞表.set_index("詞")["新詞"].to_dict()
詞數 = 5 + len(詞字典)
訓練表 = 預處理(訓練表, 詞字典)
測試表 = 預處理(測試表, 詞字典)
with open("資料/詞字典", "wb") as 档案:
	pickle.dump(詞字典, 档案)

訓練詞表 = pandas.concat([
	訓練表.loc[:, ["標識", "上句", "上句詞數"]].rename({"上句": "句", "上句詞數": "句詞數"}, axis=1).assign(上下句 = 0)
	, 訓練表.loc[:, ["標識", "下句", "下句詞數"]].rename({"下句": "句", "下句詞數": "句詞數"}, axis=1).assign(上下句 = 1)
])
訓練詞表 = 訓練詞表.loc[:, ["標識", "上下句", "句", "句詞數"]].set_index(["標識", "上下句", "句詞數"])["句"].apply(pandas.Series).stack().reset_index()
訓練詞表.columns = ["標識", "上下句", "句詞數", "詞序號", "詞"]

訓練同句詞表 = 訓練表.loc[:, ["標識", "上同句"]].rename({"上同句": "句"}, axis=1)
訓練同句詞表 = 訓練同句詞表.loc[:, ["標識", "句"]].set_index(["標識"])["句"].apply(pandas.Series).stack().reset_index()
訓練同句詞表.columns = ["標識", "同句詞序號", "同句詞"]

訓練異句詞表 = pandas.concat([
	訓練表.loc[:, ["標識", "上異句"]].rename({"上異句": "句"}, axis=1).assign(上下句 = 0)
	, 訓練表.loc[:, ["標識", "下異句"]].rename({"下異句": "句"}, axis=1).assign(上下句 = 1)
])
訓練異句詞表 = 訓練異句詞表.loc[:, ["標識", "上下句", "句"]].set_index(["標識", "上下句"])["句"].apply(pandas.Series).stack().reset_index()
訓練異句詞表.columns = ["標識", "上下句", "異句詞序號", "異句詞"]

訓練異句雙詞表 = pandas.concat([
	訓練表.loc[:, ["標識", "上雙詞異句"]].rename({"上雙詞異句": "句"}, axis=1).assign(上下句 = 0)
	, 訓練表.loc[:, ["標識", "下雙詞異句"]].rename({"下雙詞異句": "句"}, axis=1).assign(上下句 = 1)
])
訓練異句雙詞表 = 訓練異句雙詞表.loc[:, ["標識", "上下句", "句"]].set_index(["標識", "上下句"])["句"].apply(pandas.Series).stack().reset_index()
訓練異句雙詞表.columns = ["標識", "上下句", "異句雙詞序號", "異句雙詞"]

訓練異句三詞表 = pandas.concat([
	訓練表.loc[:, ["標識", "上三詞異句"]].rename({"上三詞異句": "句"}, axis=1).assign(上下句 = 0)
	, 訓練表.loc[:, ["標識", "下三詞異句"]].rename({"下三詞異句": "句"}, axis=1).assign(上下句 = 1)
])
訓練異句三詞表 = 訓練異句三詞表.loc[:, ["標識", "上下句", "句"]].set_index(["標識", "上下句"])["句"].apply(pandas.Series).stack().reset_index()
訓練異句三詞表.columns = ["標識", "上下句", "異句三詞序號", "異句三詞"]


批大小 = 128
def 取得資料表(
	某表
	, 某上下首詞特征表, 某上下末詞特征表, 某上下異句首詞特征表, 某上下異句末詞特征表
	, 某句特征表, 某異句特征表
	, 某詞特征表, 某交叉詞特征表
	, 某異句雙詞特征表, 某異句交叉雙詞特征表
	, 某異句三詞特征表, 某異句交叉三詞特征表
	, 某前後詞特征表
	, 某神模型
):
	某上句詞表 = 某表.loc[:, ["標識"]].merge(訓練詞表.loc[訓練詞表.上下句 == 0, ["標識", "詞", "詞序號"]], on="標識")
	某下句詞表 = 某表.loc[:, ["標識"]].merge(訓練詞表.loc[訓練詞表.上下句 == 1, ["標識", "詞", "詞序號"]], on="標識")
	某詞表 = pandas.concat([某上句詞表.loc[:, ["標識", "詞", "詞序號"]], 某下句詞表.loc[:, ["標識", "詞", "詞序號"]]], ignore_index=True)
	某詞資料表 = 某詞表.merge(某詞特征表, on="詞")
	某詞資料表 = 某詞資料表.統計特征("標識", [
		"詞樣本數", "詞正樣本數", "詞正樣本率"
	], ["sum", "mean", "min", "max"], "詞之")
	某交叉詞表 = 某上句詞表.loc[:, ["標識", "詞"]].rename({"詞": "上句詞"}, axis=1) \
		.merge(某下句詞表.loc[:, ["標識", "詞"]].rename({"詞": "下句詞"}, axis=1), on="標識")
	某交叉詞表 = 某交叉詞表.loc[某交叉詞表.上句詞 != 某交叉詞表.下句詞]
	某交叉詞表.loc[某交叉詞表.上句詞 > 某交叉詞表.下句詞, ["上句詞", "下句詞"]] = 某交叉詞表.loc[某交叉詞表.上句詞 > 某交叉詞表.下句詞, ["下句詞", "上句詞"]].to_numpy()
	某交叉詞資料表 = 某交叉詞表.merge(某交叉詞特征表, on=["上句詞", "下句詞"])
	某交叉詞資料表 = 某交叉詞資料表.統計特征("標識", [
		"交叉詞樣本數", "交叉詞正樣本數", "交叉詞正樣本率"
		, "異句交叉詞樣本數", "異句交叉詞正樣本數", "異句交叉詞正樣本率"
		, "異句交叉詞樣本數比", "異句交叉詞正樣本數比", "異句交叉詞正樣本率比"
	], ["sum", "mean", "min", "max"], "交叉詞之")

	某上異句詞表 = 某表.loc[:, ["標識"]].merge(訓練異句詞表.loc[訓練異句詞表.上下句 == 0, ["標識", "異句詞", "異句詞序號"]], on="標識")
	某下異句詞表 = 某表.loc[:, ["標識"]].merge(訓練異句詞表.loc[訓練異句詞表.上下句 == 1, ["標識", "異句詞", "異句詞序號"]], on="標識")
	某異句詞表 = pandas.concat([某上異句詞表.loc[:, ["標識", "異句詞", "異句詞序號"]], 某下異句詞表.loc[:, ["標識", "異句詞", "異句詞序號"]]], ignore_index=True)
	某異句詞資料表 = 某異句詞表.rename({"異句詞": "詞"}, axis=1).merge(某詞特征表, on="詞")
	某異句詞資料表 = 某異句詞資料表.統計特征("標識",[
		"異句詞樣本數", "異句詞正樣本數", "異句詞正樣本率"
		, "異句詞樣本數比", "異句詞正樣本數比", "異句詞正樣本率比"
		, "同句詞樣本數", "同句詞正樣本數", "同句詞正樣本率"
	], ["sum", "min", "max"], "異句詞之")
	某異句交叉詞表 = 某上異句詞表.loc[:, ["標識", "異句詞"]].rename({"異句詞": "上異句詞"}, axis=1) \
		.merge(某下異句詞表.loc[:, ["標識", "異句詞"]].rename({"異句詞": "下異句詞"}, axis=1), on="標識")
	某異句交叉詞表 = 某異句交叉詞表.loc[某異句交叉詞表.上異句詞 != 某異句交叉詞表.下異句詞]
	某異句交叉詞表.loc[某異句交叉詞表.上異句詞 > 某異句交叉詞表.下異句詞, ["上異句詞", "下異句詞"]] = 某異句交叉詞表.loc[某異句交叉詞表.上異句詞 > 某異句交叉詞表.下異句詞, ["下異句詞", "上異句詞"]].to_numpy()
	某異句交叉詞資料表 = 某異句交叉詞表.rename({"上異句詞": "上句詞", "下異句詞": "下句詞"}, axis=1).merge(某交叉詞特征表, on=["上句詞", "下句詞"])
	某異句交叉詞資料表 = 某異句交叉詞資料表.統計特征("標識", [
		"異句交叉詞樣本數", "異句交叉詞正樣本數", "異句交叉詞正樣本率"
		, "異句交叉詞樣本數比", "異句交叉詞正樣本數比", "異句交叉詞正樣本率比"
	], ["sum", "min", "max"], "異句交叉詞之")

	某上異句雙詞表 = 某表.loc[:, ["標識"]].merge(訓練異句雙詞表.loc[訓練異句雙詞表.上下句 == 0, ["標識", "異句雙詞"]], on="標識")
	某下異句雙詞表 = 某表.loc[:, ["標識"]].merge(訓練異句雙詞表.loc[訓練異句雙詞表.上下句 == 1, ["標識", "異句雙詞"]], on="標識")
	某異句雙詞表 = pandas.concat([某上異句雙詞表.loc[:, ["標識", "異句雙詞"]], 某下異句雙詞表.loc[:, ["標識", "異句雙詞"]]], ignore_index=True)
	某異句雙詞資料表 = 某異句雙詞表.merge(某異句雙詞特征表, on="異句雙詞")
	某異句雙詞資料表 = 某異句雙詞資料表.統計特征("標識", ["異句雙詞樣本數", "異句雙詞正樣本數", "異句雙詞正樣本率"], ["sum", "min", "max"])
	某異句交叉雙詞表 = 某上異句雙詞表.loc[:, ["標識", "異句雙詞"]].rename({"異句雙詞": "上異句雙詞"}, axis=1) \
		.merge(某下異句雙詞表.loc[:, ["標識", "異句雙詞"]].rename({"異句雙詞": "下異句雙詞"}, axis=1), on="標識")
	某異句交叉雙詞表 = 某異句交叉雙詞表.loc[某異句交叉雙詞表.上異句雙詞 != 某異句交叉雙詞表.下異句雙詞]
	某異句交叉雙詞表.loc[某異句交叉雙詞表.上異句雙詞 > 某異句交叉雙詞表.下異句雙詞, ["上異句雙詞", "下異句雙詞"]] = 某異句交叉雙詞表.loc[某異句交叉雙詞表.上異句雙詞 > 某異句交叉雙詞表.下異句雙詞, ["下異句雙詞", "上異句雙詞"]].to_numpy()
	某異句交叉雙詞資料表 = 某異句交叉雙詞表.merge(某異句交叉雙詞特征表, on=["上異句雙詞", "下異句雙詞"])
	某異句交叉雙詞資料表 = 某異句交叉雙詞資料表.統計特征("標識", ["異句交叉雙詞樣本數", "異句交叉雙詞正樣本數", "異句交叉雙詞正樣本率"], ["sum", "min", "max"])

	某上異句三詞表 = 某表.loc[:, ["標識"]].merge(訓練異句三詞表.loc[訓練異句三詞表.上下句 == 0, ["標識", "異句三詞"]], on="標識")
	某下異句三詞表 = 某表.loc[:, ["標識"]].merge(訓練異句三詞表.loc[訓練異句三詞表.上下句 == 1, ["標識", "異句三詞"]], on="標識")
	某異句三詞表 = pandas.concat([某上異句三詞表.loc[:, ["標識", "異句三詞"]], 某下異句三詞表.loc[:, ["標識", "異句三詞"]]], ignore_index=True)
	某異句三詞資料表 = 某異句三詞表.merge(某異句三詞特征表, on="異句三詞")
	某異句三詞資料表 = 某異句三詞資料表.統計特征("標識", ["異句三詞樣本數", "異句三詞正樣本數", "異句三詞正樣本率"], ["sum", "min", "max"])
	某異句交叉三詞表 = 某上異句三詞表.loc[:, ["標識", "異句三詞"]].rename({"異句三詞": "上異句三詞"}, axis=1) \
		.merge(某下異句三詞表.loc[:, ["標識", "異句三詞"]].rename({"異句三詞": "下異句三詞"}, axis=1), on="標識")
	某異句交叉三詞表 = 某異句交叉三詞表.loc[某異句交叉三詞表.上異句三詞 != 某異句交叉三詞表.下異句三詞]
	某異句交叉三詞表.loc[某異句交叉三詞表.上異句三詞 > 某異句交叉三詞表.下異句三詞, ["上異句三詞", "下異句三詞"]] = 某異句交叉三詞表.loc[某異句交叉三詞表.上異句三詞 > 某異句交叉三詞表.下異句三詞, ["下異句三詞", "上異句三詞"]].to_numpy()
	某異句交叉三詞資料表 = 某異句交叉三詞表.merge(某異句交叉三詞特征表, on=["上異句三詞", "下異句三詞"])
	某異句交叉三詞資料表 = 某異句交叉三詞資料表.統計特征("標識", ["異句交叉三詞樣本數", "異句交叉三詞正樣本數", "異句交叉三詞正樣本率"], ["sum", "min", "max"])

	某上句前後詞表 = 某上句詞表.loc[:, ["標識", "詞", "詞序號"]].rename({"詞": "前詞", "詞序號": "前詞序號"}, axis=1) \
		.merge(某上句詞表.loc[:, ["標識", "詞", "詞序號"]].rename({"詞": "後詞", "詞序號": "後詞序號"}, axis=1), on="標識")
	某上句前後詞表 = 某上句前後詞表.loc[某上句前後詞表.前詞序號 < 某上句前後詞表.後詞序號, ["標識", "前詞", "後詞"]]
	某下句前後詞表 = 某下句詞表.loc[:, ["標識", "詞", "詞序號"]].rename({"詞": "前詞", "詞序號": "前詞序號"}, axis=1) \
		.merge(某下句詞表.loc[:, ["標識", "詞", "詞序號"]].rename({"詞": "後詞", "詞序號": "後詞序號"}, axis=1), on="標識")
	某下句前後詞表 = 某下句前後詞表.loc[某下句前後詞表.前詞序號 < 某下句前後詞表.後詞序號, ["標識", "前詞", "後詞"]]
	某前後詞表 = pandas.concat([某上句前後詞表, 某下句前後詞表], ignore_index=True)
	某前後詞資料表 = 某前後詞表.merge(某前後詞特征表, on=["前詞", "後詞"])
	某前後詞資料表 = 某前後詞資料表.統計特征("標識", ["前後詞樣本數", "前後詞正樣本數", "前後詞正樣本率", "前後詞樣本數比", "前後詞正樣本數比", "前後詞正樣本率比"], ["sum", "max"])

	某表 = 某表.merge(某上下首詞特征表, on="上下首詞", how="left")
	某表 = 某表.merge(某上下末詞特征表, on="上下末詞", how="left")
	某表 = 某表.merge(某上下異句首詞特征表, on="上下異句首詞", how="left")
	某表 = 某表.merge(某上下異句末詞特征表, on="上下異句末詞", how="left")
	某表 = 某表.merge(某句特征表.add_prefix("上"), on="上句字串", how="left").merge(某句特征表.add_prefix("下"), on="下句字串", how="left")
	某表 = 某表.merge(某異句特征表.add_prefix("上"), on="上異句字串", how="left").merge(某異句特征表.add_prefix("下"), on="下異句字串", how="left")
	某表 = 某表.fillna(0)

	某資料表 = 某表.loc[:, ["標識", "標籤"
		, "交集詞數", "並集詞數", "差集詞數和", "差集詞數積", "公共前綴長", "公共後綴長", "最長公共子序列長", "最長公共子串長", "編輯距離"
		, "上下首詞樣本數", "上下首詞正樣本數", "上下首詞正樣本率", "上下末詞樣本數", "上下末詞正樣本數", "上下末詞正樣本率"
		, "上下異句首詞樣本數", "上下異句首詞正樣本數", "上下異句首詞正樣本率", "上下異句末詞樣本數", "上下異句末詞正樣本數", "上下異句末詞正樣本率"
	]]
	某資料表["詞數和"] = 某表.上句詞數 + 某表.下句詞數
	某資料表["詞數差"] = (某表.上句詞數 - 某表.下句詞數).abs()

	for 列 in [
		"句樣本數", "句正樣本數", "句正樣本率"
		, "異句樣本數", "異句正樣本數", "異句正樣本率"
	]:
		某資料表["%s_max" % 列] = 某表.loc[:, ["上%s" % 列, "下%s" % 列]].max(axis=1)

	某預測 = []
	批上下句 = []
	批下上句 = []
	for 丙, 丙列 in enumerate(某表.itertuples()):
		上下句 = [2] + 丙列.上句 + [2] + 丙列.下句
		下上句 = [2] + 丙列.下句 + [2] + 丙列.上句
		句詞數 = len(上下句)
		if 句詞數 < 句長:
			上下句 = numpy.pad(上下句, pad_width=(0, 句長 - 句詞數)).astype(numpy.int64)
			下上句 = numpy.pad(下上句, pad_width=(0, 句長 - 句詞數)).astype(numpy.int64)
		else:
			上下句 = numpy.array(上下句[:句長]).astype(numpy.int64)
			下上句 = numpy.array(下上句[:句長]).astype(numpy.int64)

		批上下句 += [上下句]
		批下上句 += [下上句]
		if len(批上下句) >= 批大小 or 丙 == len(某表) - 1:
			輸出 = 某神模型(
				torch.tensor(numpy.array(批上下句)).to(裝置)
				, torch.tensor(numpy.array(批下上句)).to(裝置)
			)
			某預測 += 輸出.data.cpu().numpy().tolist()
			批上下句 = []
			批下上句 = []

	某資料表["神預測打分"] = 某預測

	某資料表 = 某資料表.merge(某詞資料表, on="標識", how="left")
	某資料表 = 某資料表.merge(某交叉詞資料表, on="標識", how="left")
	某資料表 = 某資料表.merge(某異句詞資料表, on="標識", how="left")
	某資料表 = 某資料表.merge(某異句交叉詞資料表, on="標識", how="left")
	某資料表 = 某資料表.merge(某異句雙詞資料表, on="標識", how="left")
	某資料表 = 某資料表.merge(某異句交叉雙詞資料表, on="標識", how="left")
	某資料表 = 某資料表.merge(某異句三詞資料表, on="標識", how="left")
	某資料表 = 某資料表.merge(某異句交叉三詞資料表, on="標識", how="left")
	某資料表 = 某資料表.merge(某前後詞資料表, on="標識", how="left")

	return 某資料表

上下首詞特征表 = 訓練表.統計標準特征("上下首詞")
上下末詞特征表 = 訓練表.統計標準特征("上下末詞")
上下異句首詞特征表 = 訓練表.統計標準特征("上下異句首詞")
上下異句末詞特征表 = 訓練表.統計標準特征("上下異句末詞")

句特征表 = pandas.concat([
	訓練表.loc[:, ["上句字串", "標籤"]].rename({"上句字串": "句字串"}, axis=1)
	, 訓練表.loc[:, ["下句字串", "標籤"]].rename({"下句字串": "句字串"}, axis=1)
]).統計標準特征("句字串", "句")

異句特征表 = pandas.concat([
	訓練表.loc[:, ["上異句字串", "標籤"]].rename({"上異句字串": "異句字串"}, axis=1)
	, 訓練表.loc[:, ["下異句字串", "標籤"]].rename({"下異句字串": "異句字串"}, axis=1)
]).統計標準特征("異句字串", "異句")

上句詞表 = 訓練表.loc[:, ["標識", "標籤"]].merge(訓練詞表.loc[訓練詞表.上下句 == 0, ["標識", "詞", "詞序號"]], on="標識")
下句詞表 = 訓練表.loc[:, ["標識", "標籤"]].merge(訓練詞表.loc[訓練詞表.上下句 == 1, ["標識", "詞", "詞序號"]], on="標識")
詞表 = pandas.concat([上句詞表.loc[:, ["標籤", "詞"]], 下句詞表.loc[:, ["標籤", "詞"]]], ignore_index=True)
詞特征表 = 詞表.統計標準特征("詞")

上異句詞表 = 訓練表.loc[:, ["標識", "標籤"]].merge(訓練異句詞表.loc[訓練異句詞表.上下句 == 0, ["標識", "異句詞", "異句詞序號"]], on="標識")
下異句詞表 = 訓練表.loc[:, ["標識", "標籤"]].merge(訓練異句詞表.loc[訓練異句詞表.上下句 == 1, ["標識", "異句詞", "異句詞序號"]], on="標識")
異句詞表 = pandas.concat([上異句詞表.loc[:, ["標籤", "異句詞", "異句詞序號"]], 下異句詞表.loc[:, ["標籤", "異句詞", "異句詞序號"]]], ignore_index=True)
異句詞特征表 = 異句詞表.統計標準特征("異句詞")

同句詞表 = 訓練表.loc[:, ["標識", "標籤"]].merge(訓練同句詞表.loc[:, ["標識", "同句詞", "同句詞序號"]], on="標識")
同句詞特征表 = 同句詞表.統計標準特征("同句詞")

詞特征表 = 詞特征表.merge(異句詞特征表.rename({"異句詞": "詞"}, axis=1), on="詞", how="left")
詞特征表 = 詞特征表.merge(同句詞特征表.rename({"同句詞": "詞"}, axis=1), on="詞", how="left")
詞特征表["異句詞樣本數比"] = 詞特征表.異句詞樣本數 / 詞特征表.詞樣本數
詞特征表["異句詞正樣本數比"] = 詞特征表.異句詞正樣本數 / 詞特征表.詞正樣本數
詞特征表["異句詞正樣本率比"] = 詞特征表.異句詞正樣本率 / 詞特征表.詞正樣本率

交叉詞表 = 上句詞表.loc[:, ["標識", "標籤", "詞"]].rename({"詞": "上句詞"}, axis=1) \
	.merge(下句詞表.loc[:, ["標識", "標籤", "詞"]].rename({"詞": "下句詞"}, axis=1), on=["標識", "標籤"])
交叉詞表 = 交叉詞表.loc[交叉詞表.上句詞 != 交叉詞表.下句詞]
交叉詞表.loc[交叉詞表.上句詞 > 交叉詞表.下句詞, ["上句詞", "下句詞"]] = 交叉詞表.loc[交叉詞表.上句詞 > 交叉詞表.下句詞, ["下句詞", "上句詞"]].to_numpy()
交叉詞特征表 = 交叉詞表.統計標準特征(["上句詞", "下句詞"], "交叉詞")
交叉詞特征表 = 交叉詞特征表.merge(詞特征表.loc[:, ["詞", "詞樣本數"]].add_prefix("上句"), on="上句詞")
交叉詞特征表 = 交叉詞特征表.merge(詞特征表.loc[:, ["詞", "詞樣本數"]].add_prefix("下句"), on="下句詞")
交叉詞特征表["交叉詞樣本數"] = 交叉詞特征表.交叉詞樣本數 / (交叉詞特征表.上句詞樣本數 * 交叉詞特征表.下句詞樣本數)
交叉詞特征表 = 交叉詞特征表.loc[:, ["上句詞", "下句詞", "交叉詞樣本數", "交叉詞正樣本數", "交叉詞正樣本率"]]

異句交叉詞表 = 上異句詞表.loc[:, ["標識", "標籤", "異句詞"]].rename({"異句詞": "上異句詞"}, axis=1) \
	.merge(下異句詞表.loc[:, ["標識", "標籤", "異句詞"]].rename({"異句詞": "下異句詞"}, axis=1), on=["標識", "標籤"])
異句交叉詞表 = 異句交叉詞表.loc[異句交叉詞表.上異句詞 != 異句交叉詞表.下異句詞]
異句交叉詞表.loc[異句交叉詞表.上異句詞 > 異句交叉詞表.下異句詞, ["上異句詞", "下異句詞"]] = 異句交叉詞表.loc[異句交叉詞表.上異句詞 > 異句交叉詞表.下異句詞, ["下異句詞", "上異句詞"]].to_numpy()
異句交叉詞特征表 = 異句交叉詞表.統計標準特征(["上異句詞", "下異句詞"], "異句交叉詞")
異句交叉詞特征表 = 異句交叉詞特征表.merge(異句詞特征表.loc[:, ["異句詞", "異句詞樣本數"]].add_prefix("上"), on="上異句詞")
異句交叉詞特征表 = 異句交叉詞特征表.merge(異句詞特征表.loc[:, ["異句詞", "異句詞樣本數"]].add_prefix("下"), on="下異句詞")
異句交叉詞特征表["異句交叉詞樣本數"] = 異句交叉詞特征表.異句交叉詞樣本數 / (異句交叉詞特征表.上異句詞樣本數 * 異句交叉詞特征表.下異句詞樣本數)
異句交叉詞特征表 = 異句交叉詞特征表.loc[:, ["上異句詞", "下異句詞", "異句交叉詞樣本數", "異句交叉詞正樣本數", "異句交叉詞正樣本率"]]

交叉詞特征表 = 交叉詞特征表.merge(異句交叉詞特征表.rename({"上異句詞": "上句詞", "下異句詞": "下句詞"}, axis=1), on=["上句詞", "下句詞"], how="left")
交叉詞特征表["異句交叉詞樣本數比"] = 交叉詞特征表.異句交叉詞樣本數 / 交叉詞特征表.交叉詞樣本數
交叉詞特征表["異句交叉詞正樣本數比"] = 交叉詞特征表.異句交叉詞正樣本數 / 交叉詞特征表.交叉詞正樣本數
交叉詞特征表["異句交叉詞正樣本率比"] = 交叉詞特征表.異句交叉詞正樣本率 / 交叉詞特征表.交叉詞正樣本率

上異句雙詞表 = 訓練表.loc[:, ["標識", "標籤"]].merge(訓練異句雙詞表.loc[訓練異句雙詞表.上下句 == 0, ["標識", "異句雙詞"]], on="標識")
下異句雙詞表 = 訓練表.loc[:, ["標識", "標籤"]].merge(訓練異句雙詞表.loc[訓練異句雙詞表.上下句 == 1, ["標識", "異句雙詞"]], on="標識")
異句雙詞表 = pandas.concat([上異句雙詞表.loc[:, ["標籤", "異句雙詞"]], 下異句雙詞表.loc[:, ["標籤", "異句雙詞"]]], ignore_index=True)
異句雙詞特征表 = 異句雙詞表.統計標準特征("異句雙詞")
異句交叉雙詞表 = 上異句雙詞表.loc[:, ["標識", "標籤", "異句雙詞"]].rename({"異句雙詞": "上異句雙詞"}, axis=1) \
	.merge(下異句雙詞表.loc[:, ["標識", "標籤", "異句雙詞"]].rename({"異句雙詞": "下異句雙詞"}, axis=1), on=["標識", "標籤"])
異句交叉雙詞表 = 異句交叉雙詞表.loc[異句交叉雙詞表.上異句雙詞 != 異句交叉雙詞表.下異句雙詞]
異句交叉雙詞表.loc[異句交叉雙詞表.上異句雙詞 > 異句交叉雙詞表.下異句雙詞, ["上異句雙詞", "下異句雙詞"]] = 異句交叉雙詞表.loc[異句交叉雙詞表.上異句雙詞 > 異句交叉雙詞表.下異句雙詞, ["下異句雙詞", "上異句雙詞"]].to_numpy()
異句交叉雙詞特征表 = 異句交叉雙詞表.統計標準特征(["上異句雙詞", "下異句雙詞"], "異句交叉雙詞")
異句交叉雙詞特征表 = 異句交叉雙詞特征表.merge(異句雙詞特征表.loc[:, ["異句雙詞", "異句雙詞樣本數", "異句雙詞正樣本數"]].add_prefix("上"), on="上異句雙詞")
異句交叉雙詞特征表 = 異句交叉雙詞特征表.merge(異句雙詞特征表.loc[:, ["異句雙詞", "異句雙詞樣本數", "異句雙詞正樣本數"]].add_prefix("下"), on="下異句雙詞")
異句交叉雙詞特征表 = 異句交叉雙詞特征表.loc[:, ["上異句雙詞", "下異句雙詞", "異句交叉雙詞樣本數", "異句交叉雙詞正樣本數", "異句交叉雙詞正樣本率"]]

上異句三詞表 = 訓練表.loc[:, ["標識", "標籤"]].merge(訓練異句三詞表.loc[訓練異句三詞表.上下句 == 0, ["標識", "異句三詞"]], on="標識")
下異句三詞表 = 訓練表.loc[:, ["標識", "標籤"]].merge(訓練異句三詞表.loc[訓練異句三詞表.上下句 == 1, ["標識", "異句三詞"]], on="標識")
異句三詞表 = pandas.concat([上異句三詞表.loc[:, ["標籤", "異句三詞"]], 下異句三詞表.loc[:, ["標籤", "異句三詞"]]], ignore_index=True)
異句三詞特征表 = 異句三詞表.統計標準特征("異句三詞")
異句交叉三詞表 = 上異句三詞表.loc[:, ["標識", "標籤", "異句三詞"]].rename({"異句三詞": "上異句三詞"}, axis=1) \
	.merge(下異句三詞表.loc[:, ["標識", "標籤", "異句三詞"]].rename({"異句三詞": "下異句三詞"}, axis=1), on=["標識", "標籤"])
異句交叉三詞表 = 異句交叉三詞表.loc[異句交叉三詞表.上異句三詞 != 異句交叉三詞表.下異句三詞]
異句交叉三詞表.loc[異句交叉三詞表.上異句三詞 > 異句交叉三詞表.下異句三詞, ["上異句三詞", "下異句三詞"]] = 異句交叉三詞表.loc[異句交叉三詞表.上異句三詞 > 異句交叉三詞表.下異句三詞, ["下異句三詞", "上異句三詞"]].to_numpy()
異句交叉三詞特征表 = 異句交叉三詞表.統計標準特征(["上異句三詞", "下異句三詞"], "異句交叉三詞")
異句交叉三詞特征表 = 異句交叉三詞特征表.merge(異句三詞特征表.loc[:, ["異句三詞", "異句三詞樣本數", "異句三詞正樣本數"]].add_prefix("上"), on="上異句三詞")
異句交叉三詞特征表 = 異句交叉三詞特征表.merge(異句三詞特征表.loc[:, ["異句三詞", "異句三詞樣本數", "異句三詞正樣本數"]].add_prefix("下"), on="下異句三詞")
異句交叉三詞特征表 = 異句交叉三詞特征表.loc[:, ["上異句三詞", "下異句三詞", "異句交叉三詞樣本數", "異句交叉三詞正樣本數", "異句交叉三詞正樣本率"]]

上句前後詞表 = 上句詞表.loc[:, ["標識", "標籤", "詞", "詞序號"]].rename({"詞": "前詞", "詞序號": "前詞序號"}, axis=1) \
	.merge(上句詞表.loc[:, ["標識", "標籤", "詞", "詞序號"]].rename({"詞": "後詞", "詞序號": "後詞序號"}, axis=1), on=["標識", "標籤"])
上句前後詞表 = 上句前後詞表.loc[上句前後詞表.前詞序號 < 上句前後詞表.後詞序號, ["標識", "標籤", "前詞", "後詞"]]
下句前後詞表 = 下句詞表.loc[:, ["標識", "標籤", "詞", "詞序號"]].rename({"詞": "前詞", "詞序號": "前詞序號"}, axis=1) \
	.merge(上句詞表.loc[:, ["標識", "標籤", "詞", "詞序號"]].rename({"詞": "後詞", "詞序號": "後詞序號"}, axis=1), on=["標識", "標籤"])
下句前後詞表 = 下句前後詞表.loc[下句前後詞表.前詞序號 < 下句前後詞表.後詞序號, ["標識", "標籤", "前詞", "後詞"]]
前後詞表 = pandas.concat([上句前後詞表, 下句前後詞表], ignore_index=True)
前後詞特征表 = 前後詞表.統計標準特征(["前詞", "後詞"], "前後詞")
前後詞特征表 = 前後詞特征表 \
	.merge(詞特征表.loc[:, ["詞", "詞樣本數", "詞正樣本數", "詞正樣本率"]].add_prefix("前"), on="前詞") \
	.merge(詞特征表.loc[:, ["詞", "詞樣本數", "詞正樣本數", "詞正樣本率"]].add_prefix("後"), on="後詞")
前後詞特征表["前後詞樣本數比"] = 前後詞特征表.前後詞樣本數 / (前後詞特征表.前詞樣本數 * 前後詞特征表.後詞樣本數) * 0.5
前後詞特征表["前後詞正樣本數比"] = 前後詞特征表.前後詞正樣本數 / (前後詞特征表.前詞正樣本數 * 前後詞特征表.後詞正樣本數) ** 0.5
前後詞特征表["前後詞正樣本率比"] = 前後詞特征表.前後詞正樣本率 / (前後詞特征表.前詞正樣本率 * 前後詞特征表.後詞正樣本率) ** 0.5
前後詞特征表 = 前後詞特征表.drop({"前詞樣本數", "前詞正樣本數", "前詞正樣本率", "後詞樣本數", "後詞正樣本數", "後詞正樣本率"}, axis=1)

上下首詞特征字典 = 上下首詞特征表.set_index(["上下首詞"]).to_dict(orient="index")
上下末詞特征字典 = 上下末詞特征表.set_index(["上下末詞"]).to_dict(orient="index")
上下異句首詞特征字典 = 上下異句首詞特征表.set_index(["上下異句首詞"]).to_dict(orient="index")
上下異句末詞特征字典 = 上下異句末詞特征表.set_index(["上下異句末詞"]).to_dict(orient="index")
句特征字典 = 句特征表.set_index(["句字串"]).to_dict(orient="index")
異句特征字典 = 異句特征表.set_index(["異句字串"]).to_dict(orient="index")
詞特征字典 = 詞特征表.set_index("詞").to_dict(orient="index")
交叉詞特征字典 = 交叉詞特征表.set_index(["上句詞", "下句詞"]).to_dict(orient="index")
異句雙詞特征字典 = 異句雙詞特征表.set_index(["異句雙詞"]).to_dict(orient="index")
異句交叉雙詞特征字典 = 異句交叉雙詞特征表.set_index(["上異句雙詞", "下異句雙詞"]).to_dict(orient="index")
異句三詞特征字典 = 異句三詞特征表.set_index(["異句三詞"]).to_dict(orient="index")
異句交叉三詞特征字典 = 異句交叉三詞特征表.set_index(["上異句三詞", "下異句三詞"]).to_dict(orient="index")
前後詞特征字典 = 前後詞特征表.set_index(["前詞", "後詞"]).to_dict(orient="index")
with open("資料/特征字典", "wb") as 档案:
	pickle.dump((上下首詞特征字典, 上下末詞特征字典, 上下異句首詞特征字典, 上下異句末詞特征字典
		, 句特征字典 , 異句特征字典
		, 詞特征字典, 交叉詞特征字典
		, 異句雙詞特征字典, 異句交叉雙詞特征字典
		, 異句三詞特征字典, 異句交叉三詞特征字典
		, 前後詞特征字典)
	, 档案)

裝置 = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
損失函式 = torch.nn.BCELoss().to(裝置)
class 類別_神模型(torch.nn.Module):
	def __init__(self):
		super(類別_神模型, self).__init__()

		self.BERT層 = transformers.BertModel.from_pretrained("資料/nezha")
		self.BERT層.config.max_position_embeddings = 句長
		self.BERT層.config.vocab_size = 詞數
		self.BERT層.embeddings.position_ids = torch.tensor([range(句長)])
		詞嵌入 = torch.nn.Embedding(詞數, 嵌入維數)
		詞嵌入.weight.data[0] = self.BERT層.embeddings.word_embeddings.weight[0]
		詞嵌入.weight.data[1:5] = self.BERT層.embeddings.word_embeddings.weight[100:104]
		詞嵌入.weight.data[5:] = torch.nn.init.normal_(torch.Tensor(詞數 - 5, 嵌入維數).to(裝置)
			, mean=self.BERT層.embeddings.word_embeddings.weight[107:].mean().tolist()
			, std=self.BERT層.embeddings.word_embeddings.weight[107:].std().tolist()
		)
		self.BERT層.embeddings.word_embeddings = 詞嵌入
		
		self.線性層 = torch.nn.Linear(嵌入維數, 1)
		self.遮罩第一線性層 = torch.nn.Linear(嵌入維數, 嵌入維數)
		self.遮罩歸一化層 = torch.nn.LayerNorm(嵌入維數)
		self.遮罩第二線性層 = torch.nn.Linear(嵌入維數, 詞數)
		self.to(裝置)

	def forward(self, 某上下句輸入, 某下上句輸入, 某遮罩句輸入 = None):
		if 某遮罩句輸入 is not None:
			某輸出 = self.BERT層(某遮罩句輸入, output_attentions=False, output_hidden_states=False, return_dict=False)[0]
			某輸出 = 某輸出.flatten(0, 1)
			某輸出 = torch.relu(self.遮罩第一線性層(某輸出))
			某輸出 = self.遮罩歸一化層(某輸出)
			某輸出 = torch.softmax(self.遮罩第二線性層(某輸出), dim=1)
			return 某輸出

		某上句輸出 = self.BERT層(某上下句輸入, output_attentions=False, output_hidden_states=False, return_dict=False)[1]
		某下句輸出 = self.BERT層(某下上句輸入, output_attentions=False, output_hidden_states=False, return_dict=False)[1]
		某輸出 = 某上句輸出 + 某下句輸出
		某輸出 = torch.sigmoid(self.線性層(某輸出)).squeeze(-1)

		return 某輸出



折數 = 2
random.seed(0)
索引 = random.sample(range(len(訓練表)), len(訓練表))
訓練資料表, 測試資料表 = None, None
for 甲 in range(折數):
	甲標籤表 = 訓練表.iloc[[索引[子] for 子 in range(len(索引)) if 子 % 折數 == 甲]].reset_index(drop=True)
	甲特征表 = 訓練表.iloc[[索引[子] for 子 in range(len(索引)) if 子 % 折數 != 甲]].reset_index(drop=True)




	甲上下首詞特征表 = 甲特征表.統計標準特征("上下首詞")
	甲上下末詞特征表 = 甲特征表.統計標準特征("上下末詞")
	甲上下異句首詞特征表 = 甲特征表.統計標準特征("上下異句首詞")
	甲上下異句末詞特征表 = 甲特征表.統計標準特征("上下異句末詞")

	甲句特征表 = pandas.concat([
		甲特征表.loc[:, ["上句字串", "標籤"]].rename({"上句字串": "句字串"}, axis=1)
		, 甲特征表.loc[:, ["下句字串", "標籤"]].rename({"下句字串": "句字串"}, axis=1)
	]).統計標準特征("句字串", "句")

	甲異句特征表 = pandas.concat([
		甲特征表.loc[:, ["上異句字串", "標籤"]].rename({"上異句字串": "異句字串"}, axis=1)
		, 甲特征表.loc[:, ["下異句字串", "標籤"]].rename({"下異句字串": "異句字串"}, axis=1)
	]).統計標準特征("異句字串", "異句")




	甲上句詞表 = 甲特征表.loc[:, ["標識", "標籤"]].merge(訓練詞表.loc[訓練詞表.上下句 == 0, ["標識", "詞", "詞序號"]], on="標識")
	甲下句詞表 = 甲特征表.loc[:, ["標識", "標籤"]].merge(訓練詞表.loc[訓練詞表.上下句 == 1, ["標識", "詞", "詞序號"]], on="標識")
	甲詞表 = pandas.concat([甲上句詞表.loc[:, ["標籤", "詞"]], 甲下句詞表.loc[:, ["標籤", "詞"]]], ignore_index=True)
	甲詞特征表 = 甲詞表.統計標準特征("詞")

	甲上異句詞表 = 甲特征表.loc[:, ["標識", "標籤"]].merge(訓練異句詞表.loc[訓練異句詞表.上下句 == 0, ["標識", "異句詞", "異句詞序號"]], on="標識")
	甲下異句詞表 = 甲特征表.loc[:, ["標識", "標籤"]].merge(訓練異句詞表.loc[訓練異句詞表.上下句 == 1, ["標識", "異句詞", "異句詞序號"]], on="標識")
	甲異句詞表 = pandas.concat([甲上異句詞表.loc[:, ["標籤", "異句詞", "異句詞序號"]], 甲下異句詞表.loc[:, ["標籤", "異句詞", "異句詞序號"]]], ignore_index=True)
	甲異句詞特征表 = 甲異句詞表.統計標準特征("異句詞")

	甲同句詞表 = 甲特征表.loc[:, ["標識", "標籤"]].merge(訓練同句詞表.loc[:, ["標識", "同句詞", "同句詞序號"]], on="標識")
	甲同句詞特征表 = 甲同句詞表.統計標準特征("同句詞")

	甲詞特征表 = 甲詞特征表.merge(甲異句詞特征表.rename({"異句詞": "詞"}, axis=1), on="詞", how="left")
	甲詞特征表 = 甲詞特征表.merge(甲同句詞特征表.rename({"同句詞": "詞"}, axis=1), on="詞", how="left")
	甲詞特征表["異句詞樣本數比"] = 甲詞特征表.異句詞樣本數 / 甲詞特征表.詞樣本數
	甲詞特征表["異句詞正樣本數比"] = 甲詞特征表.異句詞正樣本數 / 甲詞特征表.詞正樣本數
	甲詞特征表["異句詞正樣本率比"] = 甲詞特征表.異句詞正樣本率 / 甲詞特征表.詞正樣本率




	甲交叉詞表 = 甲上句詞表.loc[:, ["標識", "標籤", "詞"]].rename({"詞": "上句詞"}, axis=1) \
		.merge(甲下句詞表.loc[:, ["標識", "標籤", "詞"]].rename({"詞": "下句詞"}, axis=1), on=["標識", "標籤"])
	甲交叉詞表 = 甲交叉詞表.loc[甲交叉詞表.上句詞 != 甲交叉詞表.下句詞]
	甲交叉詞表.loc[甲交叉詞表.上句詞 > 甲交叉詞表.下句詞, ["上句詞", "下句詞"]] = 甲交叉詞表.loc[甲交叉詞表.上句詞 > 甲交叉詞表.下句詞, ["下句詞", "上句詞"]].to_numpy()
	甲交叉詞特征表 = 甲交叉詞表.統計標準特征(["上句詞", "下句詞"], "交叉詞")
	甲交叉詞特征表 = 甲交叉詞特征表.merge(甲詞特征表.loc[:, ["詞", "詞樣本數"]].add_prefix("上句"), on="上句詞")
	甲交叉詞特征表 = 甲交叉詞特征表.merge(甲詞特征表.loc[:, ["詞", "詞樣本數"]].add_prefix("下句"), on="下句詞")
	甲交叉詞特征表["交叉詞樣本數"] = 甲交叉詞特征表.交叉詞樣本數 / (甲交叉詞特征表.上句詞樣本數 * 甲交叉詞特征表.下句詞樣本數)
	甲交叉詞特征表 = 甲交叉詞特征表.loc[:, ["上句詞", "下句詞", "交叉詞樣本數", "交叉詞正樣本數", "交叉詞正樣本率"]]

	甲異句交叉詞表 = 甲上異句詞表.loc[:, ["標識", "標籤", "異句詞"]].rename({"異句詞": "上異句詞"}, axis=1) \
		.merge(甲下異句詞表.loc[:, ["標識", "標籤", "異句詞"]].rename({"異句詞": "下異句詞"}, axis=1), on=["標識", "標籤"])
	甲異句交叉詞表 = 甲異句交叉詞表.loc[甲異句交叉詞表.上異句詞 != 甲異句交叉詞表.下異句詞]
	甲異句交叉詞表.loc[甲異句交叉詞表.上異句詞 > 甲異句交叉詞表.下異句詞, ["上異句詞", "下異句詞"]] = 甲異句交叉詞表.loc[甲異句交叉詞表.上異句詞 > 甲異句交叉詞表.下異句詞, ["下異句詞", "上異句詞"]].to_numpy()
	甲異句交叉詞特征表 = 甲異句交叉詞表.統計標準特征(["上異句詞", "下異句詞"], "異句交叉詞")
	甲異句交叉詞特征表 = 甲異句交叉詞特征表.merge(甲異句詞特征表.loc[:, ["異句詞", "異句詞樣本數"]].add_prefix("上"), on="上異句詞")
	甲異句交叉詞特征表 = 甲異句交叉詞特征表.merge(甲異句詞特征表.loc[:, ["異句詞", "異句詞樣本數"]].add_prefix("下"), on="下異句詞")
	甲異句交叉詞特征表["異句交叉詞樣本數"] = 甲異句交叉詞特征表.異句交叉詞樣本數 / (甲異句交叉詞特征表.上異句詞樣本數 * 甲異句交叉詞特征表.下異句詞樣本數)
	甲異句交叉詞特征表 = 甲異句交叉詞特征表.loc[:, ["上異句詞", "下異句詞", "異句交叉詞樣本數", "異句交叉詞正樣本數", "異句交叉詞正樣本率"]]

	甲交叉詞特征表 = 甲交叉詞特征表.merge(甲異句交叉詞特征表.rename({"上異句詞": "上句詞", "下異句詞": "下句詞"}, axis=1), on=["上句詞", "下句詞"], how="left")
	甲交叉詞特征表["異句交叉詞樣本數比"] = 甲交叉詞特征表.異句交叉詞樣本數 / 甲交叉詞特征表.交叉詞樣本數
	甲交叉詞特征表["異句交叉詞正樣本數比"] = 甲交叉詞特征表.異句交叉詞正樣本數 / 甲交叉詞特征表.交叉詞正樣本數
	甲交叉詞特征表["異句交叉詞正樣本率比"] = 甲交叉詞特征表.異句交叉詞正樣本率 / 甲交叉詞特征表.交叉詞正樣本率




	甲上異句雙詞表 = 甲特征表.loc[:, ["標識", "標籤"]].merge(訓練異句雙詞表.loc[訓練異句雙詞表.上下句 == 0, ["標識", "異句雙詞"]], on="標識")
	甲下異句雙詞表 = 甲特征表.loc[:, ["標識", "標籤"]].merge(訓練異句雙詞表.loc[訓練異句雙詞表.上下句 == 1, ["標識", "異句雙詞"]], on="標識")
	甲異句雙詞表 = pandas.concat([甲上異句雙詞表.loc[:, ["標籤", "異句雙詞"]], 甲下異句雙詞表.loc[:, ["標籤", "異句雙詞"]]], ignore_index=True)
	甲異句雙詞特征表 = 甲異句雙詞表.統計標準特征("異句雙詞")
	甲異句交叉雙詞表 = 甲上異句雙詞表.loc[:, ["標識", "標籤", "異句雙詞"]].rename({"異句雙詞": "上異句雙詞"}, axis=1) \
		.merge(甲下異句雙詞表.loc[:, ["標識", "標籤", "異句雙詞"]].rename({"異句雙詞": "下異句雙詞"}, axis=1), on=["標識", "標籤"])
	甲異句交叉雙詞表 = 甲異句交叉雙詞表.loc[甲異句交叉雙詞表.上異句雙詞 != 甲異句交叉雙詞表.下異句雙詞]
	甲異句交叉雙詞表.loc[甲異句交叉雙詞表.上異句雙詞 > 甲異句交叉雙詞表.下異句雙詞, ["上異句雙詞", "下異句雙詞"]] = 甲異句交叉雙詞表.loc[甲異句交叉雙詞表.上異句雙詞 > 甲異句交叉雙詞表.下異句雙詞, ["下異句雙詞", "上異句雙詞"]].to_numpy()
	甲異句交叉雙詞特征表 = 甲異句交叉雙詞表.統計標準特征(["上異句雙詞", "下異句雙詞"], "異句交叉雙詞")
	甲異句交叉雙詞特征表 = 甲異句交叉雙詞特征表.merge(甲異句雙詞特征表.loc[:, ["異句雙詞", "異句雙詞樣本數", "異句雙詞正樣本數"]].add_prefix("上"), on="上異句雙詞")
	甲異句交叉雙詞特征表 = 甲異句交叉雙詞特征表.merge(甲異句雙詞特征表.loc[:, ["異句雙詞", "異句雙詞樣本數", "異句雙詞正樣本數"]].add_prefix("下"), on="下異句雙詞")
	甲異句交叉雙詞特征表 = 甲異句交叉雙詞特征表.loc[:, ["上異句雙詞", "下異句雙詞", "異句交叉雙詞樣本數", "異句交叉雙詞正樣本數", "異句交叉雙詞正樣本率"]]

	甲上異句三詞表 = 甲特征表.loc[:, ["標識", "標籤"]].merge(訓練異句三詞表.loc[訓練異句三詞表.上下句 == 0, ["標識", "異句三詞"]], on="標識")
	甲下異句三詞表 = 甲特征表.loc[:, ["標識", "標籤"]].merge(訓練異句三詞表.loc[訓練異句三詞表.上下句 == 1, ["標識", "異句三詞"]], on="標識")
	甲異句三詞表 = pandas.concat([甲上異句三詞表.loc[:, ["標籤", "異句三詞"]], 甲下異句三詞表.loc[:, ["標籤", "異句三詞"]]], ignore_index=True)
	甲異句三詞特征表 = 甲異句三詞表.統計標準特征("異句三詞")
	甲異句交叉三詞表 = 甲上異句三詞表.loc[:, ["標識", "標籤", "異句三詞"]].rename({"異句三詞": "上異句三詞"}, axis=1) \
		.merge(甲下異句三詞表.loc[:, ["標識", "標籤", "異句三詞"]].rename({"異句三詞": "下異句三詞"}, axis=1), on=["標識", "標籤"])
	甲異句交叉三詞表 = 甲異句交叉三詞表.loc[甲異句交叉三詞表.上異句三詞 != 甲異句交叉三詞表.下異句三詞]
	甲異句交叉三詞表.loc[甲異句交叉三詞表.上異句三詞 > 甲異句交叉三詞表.下異句三詞, ["上異句三詞", "下異句三詞"]] = 甲異句交叉三詞表.loc[甲異句交叉三詞表.上異句三詞 > 甲異句交叉三詞表.下異句三詞, ["下異句三詞", "上異句三詞"]].to_numpy()
	甲異句交叉三詞特征表 = 甲異句交叉三詞表.統計標準特征(["上異句三詞", "下異句三詞"], "異句交叉三詞")
	甲異句交叉三詞特征表 = 甲異句交叉三詞特征表.merge(甲異句三詞特征表.loc[:, ["異句三詞", "異句三詞樣本數", "異句三詞正樣本數"]].add_prefix("上"), on="上異句三詞")
	甲異句交叉三詞特征表 = 甲異句交叉三詞特征表.merge(甲異句三詞特征表.loc[:, ["異句三詞", "異句三詞樣本數", "異句三詞正樣本數"]].add_prefix("下"), on="下異句三詞")
	甲異句交叉三詞特征表 = 甲異句交叉三詞特征表.loc[:, ["上異句三詞", "下異句三詞", "異句交叉三詞樣本數", "異句交叉三詞正樣本數", "異句交叉三詞正樣本率"]]




	甲上句前後詞表 = 甲上句詞表.loc[:, ["標識", "標籤", "詞", "詞序號"]].rename({"詞": "前詞", "詞序號": "前詞序號"}, axis=1) \
		.merge(甲上句詞表.loc[:, ["標識", "標籤", "詞", "詞序號"]].rename({"詞": "後詞", "詞序號": "後詞序號"}, axis=1), on=["標識", "標籤"])
	甲上句前後詞表 = 甲上句前後詞表.loc[甲上句前後詞表.前詞序號 < 甲上句前後詞表.後詞序號, ["標識", "標籤", "前詞", "後詞"]]
	甲下句前後詞表 = 甲下句詞表.loc[:, ["標識", "標籤", "詞", "詞序號"]].rename({"詞": "前詞", "詞序號": "前詞序號"}, axis=1) \
		.merge(甲上句詞表.loc[:, ["標識", "標籤", "詞", "詞序號"]].rename({"詞": "後詞", "詞序號": "後詞序號"}, axis=1), on=["標識", "標籤"])
	甲下句前後詞表 = 甲下句前後詞表.loc[甲下句前後詞表.前詞序號 < 甲下句前後詞表.後詞序號, ["標識", "標籤", "前詞", "後詞"]]
	甲前後詞表 = pandas.concat([甲上句前後詞表, 甲下句前後詞表], ignore_index=True)
	甲前後詞特征表 = 甲前後詞表.統計標準特征(["前詞", "後詞"], "前後詞")
	甲前後詞特征表 = 甲前後詞特征表 \
		.merge(甲詞特征表.loc[:, ["詞", "詞樣本數", "詞正樣本數", "詞正樣本率"]].add_prefix("前"), on="前詞") \
		.merge(甲詞特征表.loc[:, ["詞", "詞樣本數", "詞正樣本數", "詞正樣本率"]].add_prefix("後"), on="後詞")
	甲前後詞特征表["前後詞樣本數比"] = 甲前後詞特征表.前後詞樣本數 / (甲前後詞特征表.前詞樣本數 * 甲前後詞特征表.後詞樣本數) * 0.5
	甲前後詞特征表["前後詞正樣本數比"] = 甲前後詞特征表.前後詞正樣本數 / (甲前後詞特征表.前詞正樣本數 * 甲前後詞特征表.後詞正樣本數) ** 0.5
	甲前後詞特征表["前後詞正樣本率比"] = 甲前後詞特征表.前後詞正樣本率 / (甲前後詞特征表.前詞正樣本率 * 甲前後詞特征表.後詞正樣本率) ** 0.5
	甲前後詞特征表 = 甲前後詞特征表.drop({"前詞樣本數", "前詞正樣本數", "前詞正樣本率", "後詞樣本數", "後詞正樣本數", "後詞正樣本率"}, axis=1)

	for 甲表, 總表, 鍵, 列名 in [
		(甲上下首詞特征表, 上下首詞特征表, "上下首詞", "上下首詞樣本數")
		, (甲上下末詞特征表, 上下末詞特征表, "上下末詞", "上下末詞樣本數")
		, (甲上下異句首詞特征表, 上下異句首詞特征表, "上下異句首詞", "上下異句首詞樣本數")
		, (甲上下異句末詞特征表, 上下異句末詞特征表, "上下異句末詞", "上下異句末詞樣本數")
		, (甲句特征表, 句特征表, "句字串", "句樣本數"), (甲異句特征表, 異句特征表, "異句字串", "異句樣本數")
		, (甲詞特征表, 詞特征表, "詞", ["詞樣本數", "異句詞樣本數", "同句詞樣本數", "異句詞樣本數比"])
		, (甲交叉詞特征表, 交叉詞特征表, ["上句詞", "下句詞"], ["交叉詞樣本數", "異句交叉詞樣本數", "異句交叉詞樣本數比"])
		, (甲異句雙詞特征表, 異句雙詞特征表, ["異句雙詞"], ["異句雙詞樣本數"])
		, (甲異句交叉雙詞特征表, 異句交叉雙詞特征表, ["上異句雙詞", "下異句雙詞"], ["異句交叉雙詞樣本數"])
		, (甲異句三詞特征表, 異句三詞特征表, ["異句三詞"], ["異句三詞樣本數"])
		, (甲異句交叉三詞特征表, 異句交叉三詞特征表, ["上異句三詞", "下異句三詞"], ["異句交叉三詞樣本數"])
		, (甲前後詞特征表, 前後詞特征表, ["前詞", "後詞"], ["前後詞樣本數"])
	]:
		甲表.set_index(鍵, inplace=True)
		甲表[列名] = 總表.set_index(鍵)[列名]
		甲表.reset_index(inplace=True)

	甲神模型 = 類別_神模型().to(裝置)
	甲神模型.load_state_dict(torch.load("資料/神模型%d" % 甲))
	甲神模型.eval()

	甲訓練資料表 = 取得資料表(甲標籤表.copy()
		, 甲上下首詞特征表, 甲上下末詞特征表, 甲上下異句首詞特征表, 甲上下異句末詞特征表
		, 甲句特征表, 甲異句特征表
		, 甲詞特征表, 甲交叉詞特征表
		, 甲異句雙詞特征表, 甲異句交叉雙詞特征表
		, 甲異句三詞特征表, 甲異句交叉三詞特征表
		, 甲前後詞特征表
		, 甲神模型
	)
	訓練資料表 = pandas.concat([訓練資料表, 甲訓練資料表], ignore_index=True)
	
	甲測試資料表 = 取得資料表(測試表.copy()
		, 甲上下首詞特征表, 甲上下末詞特征表, 甲上下異句首詞特征表, 甲上下異句末詞特征表
		, 甲句特征表, 甲異句特征表
		, 甲詞特征表, 甲交叉詞特征表
		, 甲異句雙詞特征表, 甲異句交叉雙詞特征表
		, 甲異句三詞特征表, 甲異句交叉三詞特征表
		, 甲前後詞特征表
		, 甲神模型
	)
	測試資料表 = pandas.concat([測試資料表, 甲測試資料表], ignore_index=True)


輕模型 = lightgbm.train(train_set=lightgbm.Dataset(訓練資料表.iloc[:, 2:], label=訓練資料表.標籤)
	, num_boost_round=4000, params={"objective": "binary", "learning_rate": 0.03, "max_depth": 6, "num_leaves": 32, "verbose": -1})

with open("資料/輕模型", "wb") as 档案:
	pickle.dump(輕模型, 档案)
	
預測表 = 測試資料表.loc[:, ["標識"]]
預測表["預測打分"] = 輕模型.predict(測試資料表.iloc[:, 2:])
預測表 = 預測表.groupby("標識").mean().reset_index()
預測表 = 預測表.merge(測試表.loc[:, ["標識", "上句字串", "下句字串"]], on="標識")
預測表["字串"] = 預測表.上句字串 + "\t" + 預測表.下句字串
預測字典 = dict(zip(預測表.字串, 預測表.預測打分))
with open("資料/預測字典", "wb") as 档案:
	pickle.dump(預測字典, 档案)
