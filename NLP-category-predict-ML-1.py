
# coding: utf-8

# In[94]:

# imports, configs, etc.

import os
import sys
import re
import csv as CSV
from copy import deepcopy
import collections as CL
import itertools as IT

import warnings
warnings.filterwarnings("ignore")

import numpy as NP
from scipy import linalg as LA
from IPython.display import display
from sympy.interactive import printing
import sympy as SYM
from sympy import Matrix as MAT
from sympy.mpmath import *
printing.init_printing()

from IPython.external import mathjax; mathjax.install_mathjax()

get_ipython().magic('matplotlib inline')
from matplotlib import pyplot as PLT
from matplotlib import cm as CM
from mpl_toolkits import axes_grid1 as AG
from mpl_toolkits.mplot3d import Axes3D as AX

NP.set_printoptions(precision=3, suppress=True)
PLT.rcParams['figure.figsize'] = (11.0, 7.5)

my_font_config = {'family' : 'sans-serif',
        'color'  : '#2A52BE',
        'weight' : 'normal',
        'size'   : 14,
        }

from nltk.corpus import stopwords

DATA_DIR = "~/data"
DATA_DIR = os.path.expanduser(DATA_DIR)
PROJ_DIR = os.path.join(DATA_DIR, "mobile-apps")

get_ipython().magic("config InlineBackend.figure_format = 'svg'")


# In[95]:

print(len(stopwords.words('english')))


#### I. Data Processing

##### _In sum, the following data procesing workflow transforms the supplied raw data into data suitable for input to a machine learning algorithm. In particular, this workflow begins with a sequence of data instances, each is a raw "bag of words"; this sequence is transformed into a structured "incidence matrix" in which the data instances are represented by the rows. Each column represents an attribute or feature, which in this case is the presence or absence of a given term._

# In[96]:

labels_file = os.path.join(PROJ_DIR, "class_labels.txt")
data_file = os.path.join(PROJ_DIR, "data.txt")


# In[97]:

SW = stopwords.words('english')

import re
ptn_nwc = "[!#$%&'*+/=?`{|}~^.-]"
ptn_nwc_obj = re.compile(ptn_nwc, re.MULTILINE)

# open the two files
# read them in
# normalize: lower case the text 
# remove end-of-line whitespace
# remove punctuation
# tokenize the lines

with open(data_file, mode='r', encoding='utf-8') as fh:
    d = ( ptn_nwc_obj.sub('', line.strip().lower()).split() 
         for line in fh.readlines() )

with open(labels_file, mode='r', encoding='utf-8') as fh:
    l = [ int(line.strip()) for line in fh.readlines() ]    
    
# remove 'stop words' (using the NLTK set) &
# remove words comprised of three letters or fewer
d = (filter(lambda v: (v not in SW) & (len(v) > 4), line) for line in d)
d = deepcopy([list(line) for line in d])

# remove frequent terms common to all mobile apps:
# (generated by scraping the app summaries 
# from AppData's 1000 most popular mobiles apps)
DOMAIN_STOP_WORDS = ['android', 'free', 'iphone', 'twitter', 'download', 
                      'feature', 'features', 'applications', 'application', 
                      'user', 'users', 'version', 'versions', 'facebook', 
                      'phone', 'available', 'using', 'information', 'provide',
                      'include', 'every', 'device', 'mobile', 'friend',
                      'different', 'please', 'simple', 'email', 'share', 'follow',
                      'great', 'screen', 'provide', 'acces', 'first', 'sound', 'video',]
                         
d = (filter(lambda v: (v not in DOMAIN_STOP_WORDS), line) for line in d)

# normalize: simple word stemming
def stem(word):
    if word.endswith('s'):
        return word[:-1]
    else:
        return word

d = (list(map(stem, line)) for line in d)

d1 = deepcopy([list(line) for line in d])

lx = NP.array([len(line) for line in d1])

# ~ 75 lines have 10 words or fewer
idx = lx > 10
sum(-idx)

# so (temporarily) filter lines having 10 words or fewer &
# filter their corresponding class labels

idx = idx.tolist()
d = IT.compress(d1, idx)
l = IT.compress(l, idx)


# In[98]:

# partition the data & class labels into class I and class 0

d = deepcopy([list(line) for line in d])
l = deepcopy([line for line in l])

assert len(d) == len(l)

# shuffle both containers
idx = NP.random.permutation(NP.arange(len(d)))
d, l = NP.array(d), NP.array(l, dtype='int8')
d, l = d[idx], l[idx]

idx1 = l==1
idx0 = l==0
d1, l1 = d[idx1], l[idx1]
d0, l0 = d[idx0], l[idx0] 

L = NP.array(l)

assert d1.size == l1.size
assert d0.size == l0.size


# In[99]:

q1 = NP.array([len(line) for line in d1])
q0 = NP.array([len(line) for line in d0])

print(round(q0.mean(), 2))
print(round(q1.mean(), 2))


# In[100]:

# look at the data by class
w1 = [ word for line in d1 for word in line ]
w0 = [ word for line in d0 for word in line ]


# In[101]:

import collections as CL

words1 = CL.defaultdict(int)
words0 = CL.defaultdict(int)

for word in w1:
    words1[word] += 1

for word in w0:
    words0[word] += 1


# In[102]:

w1_freq = sorted(zip(words1.values(), words1.keys()), reverse=True)
w0_freq = sorted(zip(words0.values(), words0.keys()), reverse=True)


# In[103]:

v1 = [t[1] for t in w1_freq[:100]]
v0 = [t[1] for t in w0_freq[:100]]
v1.extend(v0)


#### II. Constructing the Feature Vector

##### from the 50 most common terms in each class

# In[104]:

def build_feature_vector(data, feature_vector):
    """
    returns: a structured 2D data array comprised of in which
        each column encodes one discrete feature; each row
        represents one data instance
    pass in: 
        (i) the data: a nested list in which each list is one data instance,
            or 'bag of words';
        (ii) a template feature vector: a list of terms, comprising a subset
            of the population whose frequency will be counted to to supply
            the values comprising each feature vector 
    this fn transforms a sequence of word bags (each bag is a python list)
        into a structured 1D NumPy array of features
    """
    fv = set(feature_vector)
    # maps each  most-frequent term to an offset in feature vector
    term_vector_lut = { t:i for i, t in enumerate(fv) }
    # remove all words from each line not in the feature_vector
    d = (filter(lambda q: q in fv, line) for line in data)
    d = deepcopy([list(line) for line in d])
    # initialize the empty 2D NumPy array returned 
    m, n = len(d), len(term_vector_lut)
    D = NP.zeros((m, n))
    dx = CL.defaultdict(int)
    c = 0
    for line in d:
        new_row = NP.zeros(len(fv))
        for w in line:
            idx = term_vector_lut[w]
            new_row[idx] += 1
        D[c,:] = new_row
        c += 1
    return D


# In[105]:

v1 = [t[1] for t in w1_freq[:50]]
v0 = [t[1] for t in w0_freq[:50]]

v1.extend(v0)


# In[106]:

D = build_feature_vector(d, v1)


# In[107]:

get_ipython().magic('timeit build_feature_vector(d, v1)')


# In[108]:

# are any attributes empty?
# (if so, remove this feature--no predictive value and will caluse 
# division by 0 when i attempt to mean center the data

feature_val_sum = D.sum(axis=0)
assert feature_val_sum.min() > 0


# In[109]:

r1 = D[0,:]
v = D[:50,:12]
# print(v)
print(D.shape)


##### save the structured data to disk

# In[110]:

NP.unique(L)
idx1 = L==1
idx0 = L==0

D1 = D[idx1,]
D0 = D[idx0,]



# In[111]:

dfs = os.path.join(PROJ_DIR, 'data_structured.csv')

with open(dfs, 'w', encoding='utf-8') as fh:
    writer = CSV.writer(fh, delimiter=',', quotechar='|', 
                quoting=CSV.QUOTE_MINIMAL)
    writer.writerows(D.tolist())


# In[112]:

def persist_structured_data(data, file_path):
    """
    returns: nothing, creates a file called 'data_structured.csv'
        in the file_path passed in
    pass in: 
        (i) 2D NumPy array
        (ii) unix absolute file path
    """
    dfs = os.path.join(file_path, 'data_structured.csv')
    with open(dfs, 'w', encoding='utf-8') as fh:
        writer = CSV.writer(fh, delimiter=',', quotechar='|', quoting=CSV.QUOTE_MINIMAL)
        writer.writerows(D.tolist())


# In[113]:

persist_structured_data(D, PROJ_DIR)


##### some simple analysis of the data to assess the general suitability of this data set for use in building a classifier

# In[114]:

import warnings
warnings.filterwarnings('ignore', r"object.__format__ with a non-empty format string is deprecated")


# In[115]:

a1 = [ (w, c) for c, w in w1_freq[:25] ]
a0 = [ (w, c) for c, w in w0_freq[:25] ]
a10 = zip(a1, a0)
H1 = '{0} most frequent terms by class'.format(len(a1))
h2a = 'class I'
h2b = 'class 0'
ula, ulb = 15 * '_', 15 * '_'
print("{0:^50}\n".format(H1))
print("{0:^20}\t{1:^30}".format(h2a, h2b))
print("{0:30}\t{1:35}".format(ula, ulb))

for itm in a10:
    print("{0} {1:32} {2}".format(' ', itm[0][0], itm[1][0]))


# In[116]:

# how many terms appear in both classes?
c1_terms = { w[0] for w in a1 }
c0_terms = { w[0] for w in a0 }

print(len(c1_terms & c0_terms))
print("terms in both classes: \n\n{0}".format(c1_terms & c0_terms))


##### frequencies of all terms in the feature vector by class

# In[117]:

idx1 = L==1
idx1 = idx1.squeeze()
idx0 = L==0
idx0 = idx0.squeeze()

d1 = D[idx1,]
d0 = D[idx0,]
s1 = d1.sum(axis=0)
s0 = d0.sum(axis=0)


# In[122]:

fig = PLT.figure(figsize=(8, 6))
ttl = "class I vs II frequencies across the Term Vector"
ax = fig.add_subplot(111, xticks=[])
ax.plot(s0, color='#FF7E00', lw=0.7, ms=None)
ax.plot(s1, color='#2E5894', lw=0.7, ms=None)
fig.text(.5, .88, ttl, ha='center', va='top', color='#062A78', fontsize=12)
ax.grid(True)


# In[ ]:

# check for degeneracy in the transformed data matrix:


# In[133]:

# by calculating the covariance matrix of the data matrix (matrix whose rows 
# is comprised of feature vectors--just first 25 most frequent terms)
D1 = D[:,:20]
C = NP.corrcoef(D1, rowvar=0)
C.shape

# a correctly computed covariance matrix will have '1's down the main diagonal &
# have a shape of n x n (from the original m x n array
dg = C.diagonal()

assert NP.trace(C) == dg.size
assert C.shape == (D1.shape[1], D1.shape[1])

NP.set_printoptions(precision=2, suppress=True, linewidth=130)
from pprint import pprint
print(C)


# fig = PLT.figure(figsize=(8, 6))
# ax = fig.add_subplot(111, xticks=[], yticks=[])
# ax.imshow(C, cmap=CM.Greys, interpolation='nearest')

# the covariance matrix, rendered below as a 'heatmap' indicates minimal feature covariance
# this is good news for the data in its current form, but it also indicates that
# PCA might not be a useful pre-processing technique for this data


#### A Few Utility Functions

# In[134]:

def standardize(data):
    """
    mean centers the data & scales it to unit variance
    """
    data_mean = data.mean(axis=0)
    data_std = data.std(axis=0)
    data -= data_mean
    data /= data_std
    return data


# In[135]:

def partition_data(data, class_labels, train_test_ratio=.9):
    """
    returns: data & class labels, split into training and test groups,
        as 2 x 2-tuples; 
        these 2 containers are suitable to pass to scikit-learn classifier
        objects
        to call their 'fit' method, pass in *tr; 
        for 'predict', pass in te[0];
        for 'score' pass in *te
    pass in: 
        data, 2D NumPy array
        class labels, 1D NumPy array
        train:test ratio: 0 < f < 1, default is 0.9
    call this function bound to two variables, 
        eg, train, test = partition_data()
    """
    # create a vector that holds the row indices
    NP.random.seed(0)
    idx = NP.random.permutation(data.shape[0])
    # now order both data and class labels arrays by idx
    D = data[idx,]
    L = class_labels[idx]
    # allocate the data to test & train partitions according to
    # the train_test_ratio passed in
    q = int(NP.ceil(train_test_ratio * D.shape[0]))
    D_tr = D[:q,:]
    D_te = D[q:,:]
    L_tr = L[:q]
    L_te = L[q:]
    assert D_tr.shape[0] + D_te.shape[0] == D.shape[0]
    assert L_tr.shape[0] + L_te.shape[0] == L.shape[0]
    # 1D array required by scikit-learn
    L_tr, L_te = NP.squeeze(L_tr), NP.squeeze(L_te)
    return (D_tr, L_tr), (D_te, L_te)


# In[136]:

def create_confmat(actual, predicted, prettyprint=1):
    """
    returns: confusion matrix displayed by 
    pass in: 2 x 1D NumPy arrays
    """
    from sympy import Matrix as MAT
    a, p = NP.squeeze(actual), NP.squeeze(predicted)
    idx0, idx1 = a==0, a==1
    x0, y0 = a[idx0], p[idx0]
    x1, y1 = a[idx1], p[idx1]
    c00 = NP.where((a==0) & (a==p))[0].size
    c11 = NP.where((a==1) & (a==p))[0].size
    c01 = NP.where((a==0) & (a!=p))[0].size
    c10 = NP.where((a==1) & (a!=p))[0].size
    CM = NP.zeros((2, 2))
    CM[0,0] = c00
    CM[1,1] = c11
    CM[0,1] = c01
    CM[1,0] = c10
    if prettyprint:
        return MAT(CM)
    else:
        return CM


# In[137]:

def fraction_correct(actual, predicted):
    """
    returns: correctly classified instances as a decimal fraction
    pass in: two 1D arrays comprised of class labels represented as integers
        'actual' is the result returned fro the call to the classifier object's
        'predict' method (passing in the unlabeled testing data)
    """
    actual, predicted = NP.squeeze(actual), NP.squeeze(predicted)
    fc = (actual.size - NP.abs(actual - predicted).sum()) / actual.size
    return round(fc, 3)


#### III. Prepare the Data for Input to a Classifier

# In[138]:

# mean center the data & standardize to unit variance
D = standardize(D)

# some assertion fixtures:
mx = D.mean(axis=0)
ms = NP.zeros(D.shape[1])
vx = D.var(axis=0)
vs = NP.ones(D.shape[1])

# assertions
NP.testing.assert_array_almost_equal(mx, ms, decimal=4)
NP.testing.assert_array_almost_equal(vx, vs, decimal=4)


# In[139]:

# shuffle the data
L = L.reshape(-1, 1)
DL = NP.hstack((D, L))
idx = NP.random.permutation(NP.arange(D.shape[0]))
DL = DL[idx,]

D, L = NP.hsplit(DL, [-1])


# In[140]:

# partition the data into training & test sets
tr, te = partition_data(D, L)


#### IV. Build the Classifiers

# In[141]:

from sklearn import svm as SVM
from sklearn.svm import SVC
from sklearn import linear_model as LM
from sklearn.grid_search import GridSearchCV
from sklearn.cross_validation import train_test_split
from sklearn.metrics import roc_curve as ROC
from sklearn.metrics import auc as AUC
from sklearn.metrics import classification_report


#### Logistic Regression

##### instantiate the logistic regressor (actually a classifier)

# In[142]:

lr = LM.LogisticRegression(C=.1, penalty='l1', tol=1e-6)


##### train this classifier on the labeled training data

# In[143]:

lr.fit(*tr)


##### use the trained classifier to predict the class of the unlabled training data

# In[144]:

lr_pred = lr.predict(te[0])

st = '(logistic regression) fraction of testing instances correctly predicted: '
print("{0}{1}".format(st, fraction_correct(lr_pred, te[1])))


#### support vector machine

##### instantiate the support vector machine classifier

# In[145]:

svc = SVM.NuSVC(
               nu=0.3,            # lower bound on % data as support vectors
               kernel='poly',      # begin w/ polynomial kernel
               degree=2,          # simplest polynomial 
               gamma=0.0,         # only relevant for other kernel types (eg, rbf); ignored otherwise
               coef0=1000,        # degree & cofe0 are the hyperparamaters for polynomial kernel
               shrinking=True, 
               probability=True,  # need to set this flag to 'True' for ROC calculation
               tol=0.0005,        # convergence criterion 
               cache_size=200, 
               verbose=True,      # sends to terminal, not ipython nb!
               max_iter=-1,       # no iteration count threshold
               random_state=None
           )


##### train the svm classifier on the labeled training data

# In[146]:

import warnings
wstr = """using a non-integer number instead of an integer will result in an error in the future"""
warnings.filterwarnings('ignore', wstr)

svc.fit(*tr)


##### use the trained classifier to predict the class of the unlabled training data

# In[147]:

svc_pred = svc.predict(te[0])

st = '(svm) fraction of testing instances correctly predicted: '
print("{0}{1}".format(st, fraction_correct(svc_pred, te[1])))


#### Evaluate Classifier Performance

##### ROC

# In[148]:

# because we have a binary classification problem, 
# we can use ROC to evaluate the quality of these models

#logistic regression
pred_prob_lr = lr.predict_proba(te[0])
false_pos_rate_lr, true_pos_rate_lr, thresholds_lr = ROC(te[1], pred_prob_lr[:,1])
roc_auc_lr = AUC(false_pos_rate_lr, true_pos_rate_lr)
print("Logisitc Regression, area under the curve: {0:>9.3f}".format(roc_auc_lr))

# svm
pred_prob_svm = svc.predict_proba(te[0])
false_pos_rate_svm, true_pos_rate_svm, thresholds_svm = ROC(te[1], pred_prob_svm[:,1])
roc_auc_svm = AUC(false_pos_rate_svm, true_pos_rate_svm)
print("SVM, area under the curve: {0:>25.3f}".format(roc_auc_svm))


# In[170]:

# plot the ROC curves for each classifier

fpr_lr, tpr_lr = false_pos_rate_lr, true_pos_rate_lr
fpr_svm, tpr_svm = false_pos_rate_svm, true_pos_rate_svm
fig = PLT.figure(figsize=(8, 6))
ax1 = fig.add_subplot(111)
ax1.plot(fpr_lr, tpr_lr, color='#FF7F49', lw=1.5)      # logistic regression ROC curve is orange
ax1.plot(fpr_svm, tpr_svm, color='#0D98BA', lw=1.5)    # svm ROC curve is blue
ax1.plot([0, 1], [0, 1], 'k--')
fig.text(.5, .88, ttl, ha='center', va='top', color='#062A78', fontsize=12)
PLT.xlim([0., 1.])
PLT.ylim([0., 1.])
PLT.xlabel('false positive rate')
PLT.ylabel('true positive rate')
ax1.grid(True)


##### Confusion Matrix

# In[171]:

# confusion matrix for svm:
create_confmat(svc_pred, te[1])


# In[172]:

# confusion matrix for logistic regression:
create_confmat(lr_pred, te[1])


##### grid search to optimize _hyperparamater selection_ (not yet run)

#### use grid search & k-fold cross-validation to optimize selection of svm hyper-paramaters

# In[173]:

# using a two-step grid search for efficiency:
    # 1st grid search: broad search over a coarse grid; then
    # 2nd sgrid search: fine-grained mesh centered on the param vals from the prior step

# C & gamma are the relevant hyperparamaters for the rbf kernel

gamma_range = NP.logspace(-2, 3, 10)
C_range = NP.logspace(-2, 3, 10)

svc = GridSearchCV(
                    estimator=SVM.SVC(kernel='rbf'),
                    param_grid=dict(gamma=gamma_range, C=C_range),
                    n_jobs=4,
                )

svc.fit(*tr)


# In[179]:

best_param_vals = svc.best_params_

print("best score from Grid Search: {0:.2f}".format(svc.best_score_))
print("\n")
print("best paramater values from Grid Search \n")
for param, val in best_param_vals.items():
    print("{0:^12}{1:.2f}".format(param, val))


# In[180]:

def get_fine_mesh_params(best_params):
    """
    returns: dict to pass in to call GridSearchCV's param_grid arg
        one key (str) for each hyper-paramr; vals are 1D NumPy arrays
        storing sequence of values
    
    pass in: dict returned from calling a GridSearchCV object's 
        (classifier) best_params_ method, one key per hyper-param;
        each val is a single (best) param value (scalar)
    """
    param_grid_fine = dict.fromkeys(best_params.keys())
    for param, val in best_params.items():
        lo = NP.log(val) - 1
        hi = NP.log(val) + 1
        param_grid_fine[param] = NP.logspace(lo, hi, 20)
    return param_grid_fine


# In[181]:

param_grid_fine = get_fine_mesh_params(svc.best_params_)


# In[182]:

svc = GridSearchCV(
                    estimator=SVM.SVC(kernel='rbf'), 
                    param_grid = param_grid_fine, 
                    n_jobs=4,
                )


# In[183]:

svc.fit(*tr)


##### now train this GridSearch-optimized trained classifier on the labeled training data

# In[184]:

svc_pred = svc.predict(te[0])

st = '(svm) fraction of testing instances correctly predicted: '
print("{0}{1}".format(st, fraction_correct(svc_pred, te[1])))


# In[185]:

st = '(svm) fraction of testing instances correctly predicted: '
print("{0}{1:.2f}".format(st, svc.score(*te)))


# In[186]:

# i just wanted to verify that the two results above agree; 
# i was not aware until i saw _score_ in the classifier instance methods
# that i could call it to get % correct on the test set,
# previously i had been calling _pred_ then comparing those results with the test set labels


##### a second grid search using a polynomial kernel

# In[187]:

# C & gamma are the relevant hyperparamaters for the rbf kernel

degree_range = NP.arange(2, 4)
coef0_range = NP.logspace(-2, 3, 10)

param_grid_coarse = dict(degree=degree_range, coef0=coef0_range)

svc = GridSearchCV(
                    estimator=SVM.NuSVC(kernel='poly', nu=0.3),   
                    param_grid=param_grid_coarse,
                    n_jobs=4,
                )

svc.fit(*tr)


# In[188]:

param_grid_fine = get_fine_mesh_params(svc.best_params_)


# In[189]:

svc = GridSearchCV(
                    estimator=SVM.SVC(kernel='rbf'), 
                    param_grid = param_grid_fine, 
                    n_jobs=4,
                )


# In[190]:

svc.fit(*tr)


##### now train this GridSearch-optimized trained classifier on the labeled training data

# In[191]:

svc_pred = svc.predict(te[0])

st = '(svm) fraction of testing instances correctly predicted: '
print("{0}{1:.2f}".format(st, svc.score(*te)))

