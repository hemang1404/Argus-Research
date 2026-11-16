

######## ITEM 3-0: pytest-dev__pytest-5262 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/src/_pytest/capture.py b/src/_pytest/capture.py
--- a/src/_pytest/capture.py
+++ b/src/_pytest/capture.py
@@ -447,6 +447,10 @@ def name(self):
         """Ensure that file.name is a string."""
         return repr(self.buffer)
 
+    @property
+    def mode(self):
+        return self.buffer.mode.replace("b", "")
+
     def __getattr__(self, name):
         return getattr(object.__getattribute__(self, "buffer"), name)
 

=== CANDIDATE PATCH
diff --git a/src/_pytest/capture.py b/src/_pytest/capture.py
--- a/src/_pytest/capture.py
+++ b/src/_pytest/capture.py
@@ -449,6 +449,17 @@
 
     def __getattr__(self, name):
         return getattr(object.__getattribute__(self, "buffer"), name)
+
+    @property
+    def mode(self):
+        """Return the underlying file mode without the binary flag.
+
+        This ensures that code checking ``out.mode`` (e.g., youtube‑dl)
+        does not see a ``'b'`` indicating binary mode, while still
+        delegating all other attribute access to the wrapped buffer.
+        """
+        m = getattr(self.buffer, "mode", "")
+        return m.replace("b", "")
 
 
 CaptureResult = collections.namedtuple("CaptureResult", ["out", "err"])



######## ITEM 3-1: pytest-dev__pytest-5262 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/src/_pytest/capture.py b/src/_pytest/capture.py
--- a/src/_pytest/capture.py
+++ b/src/_pytest/capture.py
@@ -447,6 +447,10 @@ def name(self):
         """Ensure that file.name is a string."""
         return repr(self.buffer)
 
+    @property
+    def mode(self):
+        return self.buffer.mode.replace("b", "")
+
     def __getattr__(self, name):
         return getattr(object.__getattribute__(self, "buffer"), name)
 

=== CANDIDATE PATCH
diff --git a/src/_pytest/capture.py b/src/_pytest/capture.py
--- a/src/_pytest/capture.py
+++ b/src/_pytest/capture.py
@@ -424,6 +424,11 @@
 
 class EncodedFile(object):
     errors = "strict"  # possibly needed by py3 code (issue555)
+
+    @property
+    def mode(self):
+        m = self.buffer.mode
+        return m.replace('b', '') if 'b' in m else m
 
     def __init__(self, buffer, encoding):
         self.buffer = buffer



######## ITEM 3-2: scikit-learn__scikit-learn-10844 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/sklearn/metrics/cluster/supervised.py b/sklearn/metrics/cluster/supervised.py
--- a/sklearn/metrics/cluster/supervised.py
+++ b/sklearn/metrics/cluster/supervised.py
@@ -852,11 +852,12 @@ def fowlkes_mallows_score(labels_true, labels_pred, sparse=False):
     labels_true, labels_pred = check_clusterings(labels_true, labels_pred)
     n_samples, = labels_true.shape
 
-    c = contingency_matrix(labels_true, labels_pred, sparse=True)
+    c = contingency_matrix(labels_true, labels_pred,
+                           sparse=True).astype(np.int64)
     tk = np.dot(c.data, c.data) - n_samples
     pk = np.sum(np.asarray(c.sum(axis=0)).ravel() ** 2) - n_samples
     qk = np.sum(np.asarray(c.sum(axis=1)).ravel() ** 2) - n_samples
-    return tk / np.sqrt(pk * qk) if tk != 0. else 0.
+    return np.sqrt(tk / pk) * np.sqrt(tk / qk) if tk != 0. else 0.
 
 
 def entropy(labels):

=== CANDIDATE PATCH
diff --git a/sklearn/metrics/cluster/supervised.py b/sklearn/metrics/cluster/supervised.py
--- a/sklearn/metrics/cluster/supervised.py
+++ b/sklearn/metrics/cluster/supervised.py
@@ -856,7 +856,11 @@
     tk = np.dot(c.data, c.data) - n_samples
     pk = np.sum(np.asarray(c.sum(axis=0)).ravel() ** 2) - n_samples
     qk = np.sum(np.asarray(c.sum(axis=1)).ravel() ** 2) - n_samples
-    return tk / np.sqrt(pk * qk) if tk != 0. else 0.
+    # Use a numerically stable formulation to avoid integer overflow in pk * qk.
+    if tk == 0:
+        return 0.
+    denom = np.sqrt(pk) * np.sqrt(qk)
+    return tk / denom
 
 
 def entropy(labels):



######## ITEM 3-3: scikit-learn__scikit-learn-10844 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/sklearn/metrics/cluster/supervised.py b/sklearn/metrics/cluster/supervised.py
--- a/sklearn/metrics/cluster/supervised.py
+++ b/sklearn/metrics/cluster/supervised.py
@@ -852,11 +852,12 @@ def fowlkes_mallows_score(labels_true, labels_pred, sparse=False):
     labels_true, labels_pred = check_clusterings(labels_true, labels_pred)
     n_samples, = labels_true.shape
 
-    c = contingency_matrix(labels_true, labels_pred, sparse=True)
+    c = contingency_matrix(labels_true, labels_pred,
+                           sparse=True).astype(np.int64)
     tk = np.dot(c.data, c.data) - n_samples
     pk = np.sum(np.asarray(c.sum(axis=0)).ravel() ** 2) - n_samples
     qk = np.sum(np.asarray(c.sum(axis=1)).ravel() ** 2) - n_samples
-    return tk / np.sqrt(pk * qk) if tk != 0. else 0.
+    return np.sqrt(tk / pk) * np.sqrt(tk / qk) if tk != 0. else 0.
 
 
 def entropy(labels):

=== CANDIDATE PATCH
diff --git a/sklearn/metrics/cluster/supervised.py b/sklearn/metrics/cluster/supervised.py
--- a/sklearn/metrics/cluster/supervised.py
+++ b/sklearn/metrics/cluster/supervised.py
@@ -856,7 +856,8 @@
     tk = np.dot(c.data, c.data) - n_samples
     pk = np.sum(np.asarray(c.sum(axis=0)).ravel() ** 2) - n_samples
     qk = np.sum(np.asarray(c.sum(axis=1)).ravel() ** 2) - n_samples
-    return tk / np.sqrt(pk * qk) if tk != 0. else 0.
+    # Cast to float before multiplication to avoid integer overflow
+    return tk / np.sqrt(float(pk) * float(qk)) if tk != 0. else 0.
 
 
 def entropy(labels):



######## ITEM 3-4: scikit-learn__scikit-learn-10844 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/sklearn/metrics/cluster/supervised.py b/sklearn/metrics/cluster/supervised.py
--- a/sklearn/metrics/cluster/supervised.py
+++ b/sklearn/metrics/cluster/supervised.py
@@ -852,11 +852,12 @@ def fowlkes_mallows_score(labels_true, labels_pred, sparse=False):
     labels_true, labels_pred = check_clusterings(labels_true, labels_pred)
     n_samples, = labels_true.shape
 
-    c = contingency_matrix(labels_true, labels_pred, sparse=True)
+    c = contingency_matrix(labels_true, labels_pred,
+                           sparse=True).astype(np.int64)
     tk = np.dot(c.data, c.data) - n_samples
     pk = np.sum(np.asarray(c.sum(axis=0)).ravel() ** 2) - n_samples
     qk = np.sum(np.asarray(c.sum(axis=1)).ravel() ** 2) - n_samples
-    return tk / np.sqrt(pk * qk) if tk != 0. else 0.
+    return np.sqrt(tk / pk) * np.sqrt(tk / qk) if tk != 0. else 0.
 
 
 def entropy(labels):

=== CANDIDATE PATCH
diff --git a/sklearn/metrics/cluster/supervised.py b/sklearn/metrics/cluster/supervised.py
--- a/sklearn/metrics/cluster/supervised.py
+++ b/sklearn/metrics/cluster/supervised.py
@@ -856,7 +856,13 @@
     tk = np.dot(c.data, c.data) - n_samples
     pk = np.sum(np.asarray(c.sum(axis=0)).ravel() ** 2) - n_samples
     qk = np.sum(np.asarray(c.sum(axis=1)).ravel() ** 2) - n_samples
-    return tk / np.sqrt(pk * qk) if tk != 0. else 0.
+    if tk != 0:
+        # Cast to float to avoid integer overflow in the product
+        pk_f = np.asarray(pk, dtype=np.float64)
+        qk_f = np.asarray(qk, dtype=np.float64)
+        return np.sqrt(tk / pk_f) * np.sqrt(tk / qk_f)
+    else:
+        return 0.
 
 
 def entropy(labels):



######## ITEM 3-5: scikit-learn__scikit-learn-10844 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/sklearn/metrics/cluster/supervised.py b/sklearn/metrics/cluster/supervised.py
--- a/sklearn/metrics/cluster/supervised.py
+++ b/sklearn/metrics/cluster/supervised.py
@@ -852,11 +852,12 @@ def fowlkes_mallows_score(labels_true, labels_pred, sparse=False):
     labels_true, labels_pred = check_clusterings(labels_true, labels_pred)
     n_samples, = labels_true.shape
 
-    c = contingency_matrix(labels_true, labels_pred, sparse=True)
+    c = contingency_matrix(labels_true, labels_pred,
+                           sparse=True).astype(np.int64)
     tk = np.dot(c.data, c.data) - n_samples
     pk = np.sum(np.asarray(c.sum(axis=0)).ravel() ** 2) - n_samples
     qk = np.sum(np.asarray(c.sum(axis=1)).ravel() ** 2) - n_samples
-    return tk / np.sqrt(pk * qk) if tk != 0. else 0.
+    return np.sqrt(tk / pk) * np.sqrt(tk / qk) if tk != 0. else 0.
 
 
 def entropy(labels):

=== CANDIDATE PATCH
diff --git a/sklearn/metrics/cluster/supervised.py b/sklearn/metrics/cluster/supervised.py
--- a/sklearn/metrics/cluster/supervised.py
+++ b/sklearn/metrics/cluster/supervised.py
@@ -856,7 +856,10 @@
     tk = np.dot(c.data, c.data) - n_samples
     pk = np.sum(np.asarray(c.sum(axis=0)).ravel() ** 2) - n_samples
     qk = np.sum(np.asarray(c.sum(axis=1)).ravel() ** 2) - n_samples
-    return tk / np.sqrt(pk * qk) if tk != 0. else 0.
+    if tk != 0. and pk > 0 and qk > 0:
+        return np.sqrt(tk / pk) * np.sqrt(tk / qk)
+    else:
+        return 0.
 
 
 def entropy(labels):



######## ITEM 3-6: scikit-learn__scikit-learn-10844 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/sklearn/metrics/cluster/supervised.py b/sklearn/metrics/cluster/supervised.py
--- a/sklearn/metrics/cluster/supervised.py
+++ b/sklearn/metrics/cluster/supervised.py
@@ -852,11 +852,12 @@ def fowlkes_mallows_score(labels_true, labels_pred, sparse=False):
     labels_true, labels_pred = check_clusterings(labels_true, labels_pred)
     n_samples, = labels_true.shape
 
-    c = contingency_matrix(labels_true, labels_pred, sparse=True)
+    c = contingency_matrix(labels_true, labels_pred,
+                           sparse=True).astype(np.int64)
     tk = np.dot(c.data, c.data) - n_samples
     pk = np.sum(np.asarray(c.sum(axis=0)).ravel() ** 2) - n_samples
     qk = np.sum(np.asarray(c.sum(axis=1)).ravel() ** 2) - n_samples
-    return tk / np.sqrt(pk * qk) if tk != 0. else 0.
+    return np.sqrt(tk / pk) * np.sqrt(tk / qk) if tk != 0. else 0.
 
 
 def entropy(labels):

=== CANDIDATE PATCH
diff --git a/sklearn/metrics/cluster/supervised.py b/sklearn/metrics/cluster/supervised.py
--- a/sklearn/metrics/cluster/supervised.py
+++ b/sklearn/metrics/cluster/supervised.py
@@ -856,7 +856,10 @@
     tk = np.dot(c.data, c.data) - n_samples
     pk = np.sum(np.asarray(c.sum(axis=0)).ravel() ** 2) - n_samples
     qk = np.sum(np.asarray(c.sum(axis=1)).ravel() ** 2) - n_samples
-    return tk / np.sqrt(pk * qk) if tk != 0. else 0.
+    if tk == 0.:
+        return 0.
+    # Compute the FMI in a numerically stable way
+    return np.sqrt(tk / pk) * np.sqrt(tk / qk)
 
 
 def entropy(labels):



######## ITEM 3-7: scikit-learn__scikit-learn-13496 (gemma26 s0)
=== GOLD PATCH
diff --git a/sklearn/ensemble/iforest.py b/sklearn/ensemble/iforest.py
--- a/sklearn/ensemble/iforest.py
+++ b/sklearn/ensemble/iforest.py
@@ -120,6 +120,12 @@ class IsolationForest(BaseBagging, OutlierMixin):
     verbose : int, optional (default=0)
         Controls the verbosity of the tree building process.
 
+    warm_start : bool, optional (default=False)
+        When set to ``True``, reuse the solution of the previous call to fit
+        and add more estimators to the ensemble, otherwise, just fit a whole
+        new forest. See :term:`the Glossary <warm_start>`.
+
+        .. versionadded:: 0.21
 
     Attributes
     ----------
@@ -173,7 +179,8 @@ def __init__(self,
                  n_jobs=None,
                  behaviour='old',
                  random_state=None,
-                 verbose=0):
+                 verbose=0,
+                 warm_start=False):
         super().__init__(
             base_estimator=ExtraTreeRegressor(
                 max_features=1,
@@ -185,6 +192,7 @@ def __init__(self,
             n_estimators=n_estimators,
             max_samples=max_samples,
             max_features=max_features,
+            warm_start=warm_start,
             n_jobs=n_jobs,
             random_state=random_state,
             verbose=verbose)

=== CANDIDATE PATCH
diff --git a/sklearn/ensemble/iforest.py b/sklearn/ensemble/iforest.py
--- a/sklearn/ensemble/iforest.py
+++ b/sklearn/ensemble/iforest.py
@@ -84,6 +84,11 @@
         If True, individual trees are fit on random subsets of the training
         data sampled with replacement. If False, sampling without replacement
         is performed.
+
+    warm_start : bool, optional (default=False)
+        When set to ``True``, reuse the solution of the previous call to fit
+        and add more estimators to the ensemble, otherwise, just fit a whole
+        new forest. See :term:`the Glossary <warm_start>`.
 
     n_jobs : int or None, optional (default=None)
         The number of jobs to run in parallel for both `fit` and `predict`.
@@ -170,6 +175,7 @@
                  contamination="legacy",
                  max_features=1.,
                  bootstrap=False,
+                 warm_start=False,
                  n_jobs=None,
                  behaviour='old',
                  random_state=None,
@@ -185,6 +191,7 @@
             n_estimators=n_estimators,
             max_samples=max_samples,
             max_features=max_features,
+            warm_start=warm_start,
             n_jobs=n_jobs,
             random_state=random_state,
             verbose=verbose)



######## ITEM 3-8: scikit-learn__scikit-learn-13496 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/sklearn/ensemble/iforest.py b/sklearn/ensemble/iforest.py
--- a/sklearn/ensemble/iforest.py
+++ b/sklearn/ensemble/iforest.py
@@ -120,6 +120,12 @@ class IsolationForest(BaseBagging, OutlierMixin):
     verbose : int, optional (default=0)
         Controls the verbosity of the tree building process.
 
+    warm_start : bool, optional (default=False)
+        When set to ``True``, reuse the solution of the previous call to fit
+        and add more estimators to the ensemble, otherwise, just fit a whole
+        new forest. See :term:`the Glossary <warm_start>`.
+
+        .. versionadded:: 0.21
 
     Attributes
     ----------
@@ -173,7 +179,8 @@ def __init__(self,
                  n_jobs=None,
                  behaviour='old',
                  random_state=None,
-                 verbose=0):
+                 verbose=0,
+                 warm_start=False):
         super().__init__(
             base_estimator=ExtraTreeRegressor(
                 max_features=1,
@@ -185,6 +192,7 @@ def __init__(self,
             n_estimators=n_estimators,
             max_samples=max_samples,
             max_features=max_features,
+            warm_start=warm_start,
             n_jobs=n_jobs,
             random_state=random_state,
             verbose=verbose)

=== CANDIDATE PATCH
diff --git a/sklearn/ensemble/iforest.py b/sklearn/ensemble/iforest.py
--- a/sklearn/ensemble/iforest.py
+++ b/sklearn/ensemble/iforest.py
@@ -171,6 +171,7 @@
                  max_features=1.,
                  bootstrap=False,
                  n_jobs=None,
+                 warm_start=False,
                  behaviour='old',
                  random_state=None,
                  verbose=0):
@@ -187,7 +188,8 @@
             max_features=max_features,
             n_jobs=n_jobs,
             random_state=random_state,
-            verbose=verbose)
+            verbose=verbose,
+            warm_start=warm_start)
 
         self.behaviour = behaviour
         self.contamination = contamination



######## ITEM 3-9: scikit-learn__scikit-learn-13496 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/sklearn/ensemble/iforest.py b/sklearn/ensemble/iforest.py
--- a/sklearn/ensemble/iforest.py
+++ b/sklearn/ensemble/iforest.py
@@ -120,6 +120,12 @@ class IsolationForest(BaseBagging, OutlierMixin):
     verbose : int, optional (default=0)
         Controls the verbosity of the tree building process.
 
+    warm_start : bool, optional (default=False)
+        When set to ``True``, reuse the solution of the previous call to fit
+        and add more estimators to the ensemble, otherwise, just fit a whole
+        new forest. See :term:`the Glossary <warm_start>`.
+
+        .. versionadded:: 0.21
 
     Attributes
     ----------
@@ -173,7 +179,8 @@ def __init__(self,
                  n_jobs=None,
                  behaviour='old',
                  random_state=None,
-                 verbose=0):
+                 verbose=0,
+                 warm_start=False):
         super().__init__(
             base_estimator=ExtraTreeRegressor(
                 max_features=1,
@@ -185,6 +192,7 @@ def __init__(self,
             n_estimators=n_estimators,
             max_samples=max_samples,
             max_features=max_features,
+            warm_start=warm_start,
             n_jobs=n_jobs,
             random_state=random_state,
             verbose=verbose)

=== CANDIDATE PATCH
diff --git a/sklearn/ensemble/iforest.py b/sklearn/ensemble/iforest.py
--- a/sklearn/ensemble/iforest.py
+++ b/sklearn/ensemble/iforest.py
@@ -170,6 +170,7 @@
                  contamination="legacy",
                  max_features=1.,
                  bootstrap=False,
+                 warm_start=False,
                  n_jobs=None,
                  behaviour='old',
                  random_state=None,
@@ -185,6 +186,7 @@
             n_estimators=n_estimators,
             max_samples=max_samples,
             max_features=max_features,
+            warm_start=warm_start,
             n_jobs=n_jobs,
             random_state=random_state,
             verbose=verbose)



######## ITEM 3-10: scikit-learn__scikit-learn-13496 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/sklearn/ensemble/iforest.py b/sklearn/ensemble/iforest.py
--- a/sklearn/ensemble/iforest.py
+++ b/sklearn/ensemble/iforest.py
@@ -120,6 +120,12 @@ class IsolationForest(BaseBagging, OutlierMixin):
     verbose : int, optional (default=0)
         Controls the verbosity of the tree building process.
 
+    warm_start : bool, optional (default=False)
+        When set to ``True``, reuse the solution of the previous call to fit
+        and add more estimators to the ensemble, otherwise, just fit a whole
+        new forest. See :term:`the Glossary <warm_start>`.
+
+        .. versionadded:: 0.21
 
     Attributes
     ----------
@@ -173,7 +179,8 @@ def __init__(self,
                  n_jobs=None,
                  behaviour='old',
                  random_state=None,
-                 verbose=0):
+                 verbose=0,
+                 warm_start=False):
         super().__init__(
             base_estimator=ExtraTreeRegressor(
                 max_features=1,
@@ -185,6 +192,7 @@ def __init__(self,
             n_estimators=n_estimators,
             max_samples=max_samples,
             max_features=max_features,
+            warm_start=warm_start,
             n_jobs=n_jobs,
             random_state=random_state,
             verbose=verbose)

=== CANDIDATE PATCH
diff --git a/sklearn/ensemble/iforest.py b/sklearn/ensemble/iforest.py
--- a/sklearn/ensemble/iforest.py
+++ b/sklearn/ensemble/iforest.py
@@ -171,6 +171,7 @@
                  max_features=1.,
                  bootstrap=False,
                  n_jobs=None,
+                 warm_start=False,
                  behaviour='old',
                  random_state=None,
                  verbose=0):
@@ -186,6 +187,7 @@
             max_samples=max_samples,
             max_features=max_features,
             n_jobs=n_jobs,
+            warm_start=warm_start,
             random_state=random_state,
             verbose=verbose)
 



######## ITEM 3-11: scikit-learn__scikit-learn-13496 (gpt-oss-20b s2)
=== GOLD PATCH
diff --git a/sklearn/ensemble/iforest.py b/sklearn/ensemble/iforest.py
--- a/sklearn/ensemble/iforest.py
+++ b/sklearn/ensemble/iforest.py
@@ -120,6 +120,12 @@ class IsolationForest(BaseBagging, OutlierMixin):
     verbose : int, optional (default=0)
         Controls the verbosity of the tree building process.
 
+    warm_start : bool, optional (default=False)
+        When set to ``True``, reuse the solution of the previous call to fit
+        and add more estimators to the ensemble, otherwise, just fit a whole
+        new forest. See :term:`the Glossary <warm_start>`.
+
+        .. versionadded:: 0.21
 
     Attributes
     ----------
@@ -173,7 +179,8 @@ def __init__(self,
                  n_jobs=None,
                  behaviour='old',
                  random_state=None,
-                 verbose=0):
+                 verbose=0,
+                 warm_start=False):
         super().__init__(
             base_estimator=ExtraTreeRegressor(
                 max_features=1,
@@ -185,6 +192,7 @@ def __init__(self,
             n_estimators=n_estimators,
             max_samples=max_samples,
             max_features=max_features,
+            warm_start=warm_start,
             n_jobs=n_jobs,
             random_state=random_state,
             verbose=verbose)

=== CANDIDATE PATCH
diff --git a/sklearn/ensemble/iforest.py b/sklearn/ensemble/iforest.py
--- a/sklearn/ensemble/iforest.py
+++ b/sklearn/ensemble/iforest.py
@@ -111,6 +111,10 @@
            ``behaviour`` parameter will be deprecated in 0.22 and removed in
            0.24.
 
+    warm_start : bool, optional (default=False)
+        When set to ``True``, reuse the solution of the previous call to fit
+        and add more estimators to the ensemble, otherwise, just fit a whole
+        new forest. See :term:`the Glossary <warm_start>`.
     random_state : int, RandomState instance or None, optional (default=None)
         If int, random_state is the seed used by the random number generator;
         If RandomState instance, random_state is the random number generator;
@@ -172,6 +176,7 @@
                  bootstrap=False,
                  n_jobs=None,
                  behaviour='old',
+                 warm_start=False,
                  random_state=None,
                  verbose=0):
         super().__init__(
@@ -182,6 +187,7 @@
             # here above max_features has no links with self.max_features
             bootstrap=bootstrap,
             bootstrap_features=False,
+            warm_start=warm_start,
             n_estimators=n_estimators,
             max_samples=max_samples,
             max_features=max_features,



######## ITEM 3-12: scikit-learn__scikit-learn-14053 (gemma26 s1)
=== GOLD PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,7 +890,8 @@ def export_text(decision_tree, feature_names=None, max_depth=10,
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        feature_names_ = [feature_names[i] if i != _tree.TREE_UNDEFINED
+                          else None for i in tree_.feature]
     else:
         feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
 

=== CANDIDATE PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -889,10 +889,8 @@
     else:
         value_fmt = "{}{} value: {}\n"
 
-    if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
-    else:
-        feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
+    if feature_names is None:
+        feature_names = ["feature_{}".format(i) for i in range(tree_.n_features)]
 
     export_text.report = ""
 
@@ -928,7 +926,7 @@
             info_fmt_right = info_fmt
 
             if tree_.feature[node] != _tree.TREE_UNDEFINED:
-                name = feature_names_[node]
+                name = feature_names[tree_.feature[node]]
                 threshold = tree_.threshold[node]
                 threshold = "{1:.{0}f}".format(decimals, threshold)
                 export_text.report += right_child_fmt.format(indent,



######## ITEM 3-13: scikit-learn__scikit-learn-14053 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,7 +890,8 @@ def export_text(decision_tree, feature_names=None, max_depth=10,
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        feature_names_ = [feature_names[i] if i != _tree.TREE_UNDEFINED
+                          else None for i in tree_.feature]
     else:
         feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
 

=== CANDIDATE PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,9 +890,16 @@
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        # Safely map feature indices to names, handling undefined leaf nodes.
+        feature_names_ = [
+            feature_names[i] if i != _tree.TREE_UNDEFINED else ""
+            for i in tree_.feature
+        ]
     else:
-        feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
+        feature_names_ = [
+            "feature_{}".format(i) if i != _tree.TREE_UNDEFINED else ""
+            for i in tree_.feature
+        ]
 
     export_text.report = ""
 



######## ITEM 3-14: scikit-learn__scikit-learn-14053 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,7 +890,8 @@ def export_text(decision_tree, feature_names=None, max_depth=10,
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        feature_names_ = [feature_names[i] if i != _tree.TREE_UNDEFINED
+                          else None for i in tree_.feature]
     else:
         feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
 

=== CANDIDATE PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,7 +890,14 @@
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        # Map feature indices to names, handling leaf nodes where feature is undefined.
+        feature_names_ = []
+        for i in tree_.feature:
+            if i == _tree.TREE_UNDEFINED:
+                # Placeholder for leaf nodes; it will never be used for printing.
+                feature_names_.append("")
+            else:
+                feature_names_.append(feature_names[i])
     else:
         feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
 



######## ITEM 3-15: scikit-learn__scikit-learn-14053 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,7 +890,8 @@ def export_text(decision_tree, feature_names=None, max_depth=10,
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        feature_names_ = [feature_names[i] if i != _tree.TREE_UNDEFINED
+                          else None for i in tree_.feature]
     else:
         feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
 

=== CANDIDATE PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,9 +890,17 @@
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        # Guard against TREE_UNDEFINED entries (leaf nodes) which would cause
+        # an IndexError when the tree has a single feature.
+        feature_names_ = [
+            feature_names[feat] if feat != _tree.TREE_UNDEFINED else ""
+            for feat in tree_.feature
+        ]
     else:
-        feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
+        feature_names_ = [
+            "feature_{}".format(feat) if feat != _tree.TREE_UNDEFINED else ""
+            for feat in tree_.feature
+        ]
 
     export_text.report = ""
 



######## ITEM 3-16: scikit-learn__scikit-learn-14053 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,7 +890,8 @@ def export_text(decision_tree, feature_names=None, max_depth=10,
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        feature_names_ = [feature_names[i] if i != _tree.TREE_UNDEFINED
+                          else None for i in tree_.feature]
     else:
         feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
 

=== CANDIDATE PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,7 +890,7 @@
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        feature_names_ = [feature_names[i] if i >= 0 else "" for i in tree_.feature]
     else:
         feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
 



######## ITEM 3-17: scikit-learn__scikit-learn-14053 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,7 +890,8 @@ def export_text(decision_tree, feature_names=None, max_depth=10,
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        feature_names_ = [feature_names[i] if i != _tree.TREE_UNDEFINED
+                          else None for i in tree_.feature]
     else:
         feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
 

=== CANDIDATE PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,7 +890,8 @@
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        feature_names_ = [feature_names[i] if i >= 0 else "feature_{}".format(i)
+                          for i in tree_.feature]
     else:
         feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
 



######## ITEM 3-18: scikit-learn__scikit-learn-14053 (gpt-oss-20b s2)
=== GOLD PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,7 +890,8 @@ def export_text(decision_tree, feature_names=None, max_depth=10,
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        feature_names_ = [feature_names[i] if i != _tree.TREE_UNDEFINED
+                          else None for i in tree_.feature]
     else:
         feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
 

=== CANDIDATE PATCH
diff --git a/sklearn/tree/export.py b/sklearn/tree/export.py
--- a/sklearn/tree/export.py
+++ b/sklearn/tree/export.py
@@ -890,9 +890,9 @@
         value_fmt = "{}{} value: {}\n"
 
     if feature_names:
-        feature_names_ = [feature_names[i] for i in tree_.feature]
+        feature_names_ = [feature_names[i] if i >= 0 else None for i in tree_.feature]
     else:
-        feature_names_ = ["feature_{}".format(i) for i in tree_.feature]
+        feature_names_ = ["feature_{}".format(i) if i >= 0 else None for i in tree_.feature]
 
     export_text.report = ""
 



######## ITEM 3-19: scikit-learn__scikit-learn-14894 (gemma26 s0)
=== GOLD PATCH
diff --git a/sklearn/svm/base.py b/sklearn/svm/base.py
--- a/sklearn/svm/base.py
+++ b/sklearn/svm/base.py
@@ -287,11 +287,14 @@ def _sparse_fit(self, X, y, sample_weight, solver_type, kernel,
         n_SV = self.support_vectors_.shape[0]
 
         dual_coef_indices = np.tile(np.arange(n_SV), n_class)
-        dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
-                                     dual_coef_indices.size / n_class)
-        self.dual_coef_ = sp.csr_matrix(
-            (dual_coef_data, dual_coef_indices, dual_coef_indptr),
-            (n_class, n_SV))
+        if not n_SV:
+            self.dual_coef_ = sp.csr_matrix([])
+        else:
+            dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
+                                         dual_coef_indices.size / n_class)
+            self.dual_coef_ = sp.csr_matrix(
+                (dual_coef_data, dual_coef_indices, dual_coef_indptr),
+                (n_class, n_SV))
 
     def predict(self, X):
         """Perform regression on samples in X.

=== CANDIDATE PATCH
diff --git a/sklearn/svm/base.py b/sklearn/svm/base.py
--- a/sklearn/svm/base.py
+++ b/sklearn/svm/base.py
@@ -286,12 +286,15 @@
             n_class = 1
         n_SV = self.support_vectors_.shape[0]
 
-        dual_coef_indices = np.tile(np.arange(n_SV), n_class)
-        dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
-                                     dual_coef_indices.size / n_class)
-        self.dual_coef_ = sp.csr_matrix(
-            (dual_coef_data, dual_coef_indices, dual_coef_indptr),
-            (n_class, n_SV))
+        if n_SV > 0:
+            dual_coef_indices = np.tile(np.arange(n_SV), n_class)
+            dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
+                                         dual_coef_indices.size / n_class)
+            self.dual_coef_ = sp.csr_matrix(
+                (dual_coef_data, dual_coef_indices, dual_coef_indptr),
+                (n_class, n_SV))
+        else:
+            self.dual_coef_ = sp.csr_matrix((n_class, 0))
 
     def predict(self, X):
         """Perform regression on samples in X.



######## ITEM 3-20: scikit-learn__scikit-learn-14894 (gemma26 s1)
=== GOLD PATCH
diff --git a/sklearn/svm/base.py b/sklearn/svm/base.py
--- a/sklearn/svm/base.py
+++ b/sklearn/svm/base.py
@@ -287,11 +287,14 @@ def _sparse_fit(self, X, y, sample_weight, solver_type, kernel,
         n_SV = self.support_vectors_.shape[0]
 
         dual_coef_indices = np.tile(np.arange(n_SV), n_class)
-        dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
-                                     dual_coef_indices.size / n_class)
-        self.dual_coef_ = sp.csr_matrix(
-            (dual_coef_data, dual_coef_indices, dual_coef_indptr),
-            (n_class, n_SV))
+        if not n_SV:
+            self.dual_coef_ = sp.csr_matrix([])
+        else:
+            dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
+                                         dual_coef_indices.size / n_class)
+            self.dual_coef_ = sp.csr_matrix(
+                (dual_coef_data, dual_coef_indices, dual_coef_indptr),
+                (n_class, n_SV))
 
     def predict(self, X):
         """Perform regression on samples in X.

=== CANDIDATE PATCH
diff --git a/sklearn/svm/base.py b/sklearn/svm/base.py
--- a/sklearn/svm/base.py
+++ b/sklearn/svm/base.py
@@ -286,12 +286,15 @@
             n_class = 1
         n_SV = self.support_vectors_.shape[0]
 
-        dual_coef_indices = np.tile(np.arange(n_SV), n_class)
-        dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
-                                     dual_coef_indices.size / n_class)
-        self.dual_coef_ = sp.csr_matrix(
-            (dual_coef_data, dual_coef_indices, dual_coef_indptr),
-            (n_class, n_SV))
+        if n_SV == 0:
+            self.dual_coef_ = sp.csr_matrix((n_class, 0))
+        else:
+            dual_coef_indices = np.tile(np.arange(n_SV), n_class)
+            dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
+                                         dual_coef_indices.size / n_class)
+            self.dual_coef_ = sp.csr_matrix(
+                (dual_coef_data, dual_coef_indices, dual_coef_indptr),
+                (n_class, n_SV))
 
     def predict(self, X):
         """Perform regression on samples in X.



######## ITEM 3-21: scikit-learn__scikit-learn-14894 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/sklearn/svm/base.py b/sklearn/svm/base.py
--- a/sklearn/svm/base.py
+++ b/sklearn/svm/base.py
@@ -287,11 +287,14 @@ def _sparse_fit(self, X, y, sample_weight, solver_type, kernel,
         n_SV = self.support_vectors_.shape[0]
 
         dual_coef_indices = np.tile(np.arange(n_SV), n_class)
-        dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
-                                     dual_coef_indices.size / n_class)
-        self.dual_coef_ = sp.csr_matrix(
-            (dual_coef_data, dual_coef_indices, dual_coef_indptr),
-            (n_class, n_SV))
+        if not n_SV:
+            self.dual_coef_ = sp.csr_matrix([])
+        else:
+            dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
+                                         dual_coef_indices.size / n_class)
+            self.dual_coef_ = sp.csr_matrix(
+                (dual_coef_data, dual_coef_indices, dual_coef_indptr),
+                (n_class, n_SV))
 
     def predict(self, X):
         """Perform regression on samples in X.

=== CANDIDATE PATCH
diff --git a/sklearn/svm/base.py b/sklearn/svm/base.py
--- a/sklearn/svm/base.py
+++ b/sklearn/svm/base.py
@@ -286,9 +286,17 @@
             n_class = 1
         n_SV = self.support_vectors_.shape[0]
 
-        dual_coef_indices = np.tile(np.arange(n_SV), n_class)
-        dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
-                                     dual_coef_indices.size / n_class)
+        # Handle the case with no support vectors to avoid division by zero.
+        if n_SV == 0:
+            dual_coef_indices = np.empty(0, dtype=int)
+            # For an empty CSR matrix each row has zero entries,
+            # so the indptr array should be zeros of length n_class + 1.
+            dual_coef_indptr = np.zeros(n_class + 1, dtype=int)
+        else:
+            dual_coef_indices = np.tile(np.arange(n_SV), n_class)
+            # Use integer step size to construct the indptr correctly.
+            dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
+                                         dual_coef_indices.size // n_class)
         self.dual_coef_ = sp.csr_matrix(
             (dual_coef_data, dual_coef_indices, dual_coef_indptr),
             (n_class, n_SV))



######## ITEM 3-22: scikit-learn__scikit-learn-14894 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/sklearn/svm/base.py b/sklearn/svm/base.py
--- a/sklearn/svm/base.py
+++ b/sklearn/svm/base.py
@@ -287,11 +287,14 @@ def _sparse_fit(self, X, y, sample_weight, solver_type, kernel,
         n_SV = self.support_vectors_.shape[0]
 
         dual_coef_indices = np.tile(np.arange(n_SV), n_class)
-        dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
-                                     dual_coef_indices.size / n_class)
-        self.dual_coef_ = sp.csr_matrix(
-            (dual_coef_data, dual_coef_indices, dual_coef_indptr),
-            (n_class, n_SV))
+        if not n_SV:
+            self.dual_coef_ = sp.csr_matrix([])
+        else:
+            dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
+                                         dual_coef_indices.size / n_class)
+            self.dual_coef_ = sp.csr_matrix(
+                (dual_coef_data, dual_coef_indices, dual_coef_indptr),
+                (n_class, n_SV))
 
     def predict(self, X):
         """Perform regression on samples in X.

=== CANDIDATE PATCH
diff --git a/sklearn/svm/base.py b/sklearn/svm/base.py
--- a/sklearn/svm/base.py
+++ b/sklearn/svm/base.py
@@ -286,12 +286,22 @@
             n_class = 1
         n_SV = self.support_vectors_.shape[0]
 
-        dual_coef_indices = np.tile(np.arange(n_SV), n_class)
-        dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
-                                     dual_coef_indices.size / n_class)
-        self.dual_coef_ = sp.csr_matrix(
-            (dual_coef_data, dual_coef_indices, dual_coef_indptr),
-            (n_class, n_SV))
+        # Handle the case with no support vectors (n_SV == 0) or a single
+        # class (n_class == 0) gracefully. In such situations libsvm returns
+        # empty arrays and we should create an empty CSR matrix to avoid
+        # division by zero errors.
+        if n_SV == 0 or n_class == 0:
+            # Create an empty CSR matrix with the appropriate shape.
+            self.dual_coef_ = sp.csr_matrix((n_class, n_SV))
+        else:
+            dual_coef_indices = np.tile(np.arange(n_SV), n_class)
+            # Use integer division to obtain an integer step size.
+            step = dual_coef_indices.size // n_class
+            dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
+                                         step)
+            self.dual_coef_ = sp.csr_matrix(
+                (dual_coef_data, dual_coef_indices, dual_coef_indptr),
+                (n_class, n_SV))
 
     def predict(self, X):
         """Perform regression on samples in X.



######## ITEM 3-23: scikit-learn__scikit-learn-14894 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/sklearn/svm/base.py b/sklearn/svm/base.py
--- a/sklearn/svm/base.py
+++ b/sklearn/svm/base.py
@@ -287,11 +287,14 @@ def _sparse_fit(self, X, y, sample_weight, solver_type, kernel,
         n_SV = self.support_vectors_.shape[0]
 
         dual_coef_indices = np.tile(np.arange(n_SV), n_class)
-        dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
-                                     dual_coef_indices.size / n_class)
-        self.dual_coef_ = sp.csr_matrix(
-            (dual_coef_data, dual_coef_indices, dual_coef_indptr),
-            (n_class, n_SV))
+        if not n_SV:
+            self.dual_coef_ = sp.csr_matrix([])
+        else:
+            dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
+                                         dual_coef_indices.size / n_class)
+            self.dual_coef_ = sp.csr_matrix(
+                (dual_coef_data, dual_coef_indices, dual_coef_indptr),
+                (n_class, n_SV))
 
     def predict(self, X):
         """Perform regression on samples in X.

=== CANDIDATE PATCH
diff --git a/sklearn/svm/base.py b/sklearn/svm/base.py
--- a/sklearn/svm/base.py
+++ b/sklearn/svm/base.py
@@ -286,12 +286,19 @@
             n_class = 1
         n_SV = self.support_vectors_.shape[0]
 
-        dual_coef_indices = np.tile(np.arange(n_SV), n_class)
-        dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
-                                     dual_coef_indices.size / n_class)
-        self.dual_coef_ = sp.csr_matrix(
-            (dual_coef_data, dual_coef_indices, dual_coef_indptr),
-            (n_class, n_SV))
+        # Handle the case with no support vectors (empty model).
+        if n_SV == 0:
+            # Empty dual coefficient matrix with appropriate shape.
+            self.dual_coef_ = sp.csr_matrix((n_class, 0))
+        else:
+            dual_coef_indices = np.tile(np.arange(n_SV), n_class)
+            # Use integer division to compute the step size for indptr.
+            step = dual_coef_indices.size // n_class
+            dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
+                                         step)
+            self.dual_coef_ = sp.csr_matrix(
+                (dual_coef_data, dual_coef_indices, dual_coef_indptr),
+                (n_class, n_SV))
 
     def predict(self, X):
         """Perform regression on samples in X.



######## ITEM 3-24: scikit-learn__scikit-learn-14894 (gpt-oss-20b s2)
=== GOLD PATCH
diff --git a/sklearn/svm/base.py b/sklearn/svm/base.py
--- a/sklearn/svm/base.py
+++ b/sklearn/svm/base.py
@@ -287,11 +287,14 @@ def _sparse_fit(self, X, y, sample_weight, solver_type, kernel,
         n_SV = self.support_vectors_.shape[0]
 
         dual_coef_indices = np.tile(np.arange(n_SV), n_class)
-        dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
-                                     dual_coef_indices.size / n_class)
-        self.dual_coef_ = sp.csr_matrix(
-            (dual_coef_data, dual_coef_indices, dual_coef_indptr),
-            (n_class, n_SV))
+        if not n_SV:
+            self.dual_coef_ = sp.csr_matrix([])
+        else:
+            dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
+                                         dual_coef_indices.size / n_class)
+            self.dual_coef_ = sp.csr_matrix(
+                (dual_coef_data, dual_coef_indices, dual_coef_indptr),
+                (n_class, n_SV))
 
     def predict(self, X):
         """Perform regression on samples in X.

=== CANDIDATE PATCH
diff --git a/sklearn/svm/base.py b/sklearn/svm/base.py
--- a/sklearn/svm/base.py
+++ b/sklearn/svm/base.py
@@ -286,12 +286,17 @@
             n_class = 1
         n_SV = self.support_vectors_.shape[0]
 
-        dual_coef_indices = np.tile(np.arange(n_SV), n_class)
-        dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
-                                     dual_coef_indices.size / n_class)
-        self.dual_coef_ = sp.csr_matrix(
-            (dual_coef_data, dual_coef_indices, dual_coef_indptr),
-            (n_class, n_SV))
+        # Handle case with no support vectors to avoid division by zero
+        if n_SV == 0:
+            # Create an empty CSR matrix with shape (n_class, 0)
+            self.dual_coef_ = sp.csr_matrix((n_class, 0))
+        else:
+            dual_coef_indices = np.tile(np.arange(n_SV), n_class)
+            dual_coef_indptr = np.arange(0, dual_coef_indices.size + 1,
+                                         dual_coef_indices.size / n_class)
+            self.dual_coef_ = sp.csr_matrix(
+                (dual_coef_data, dual_coef_indices, dual_coef_indptr),
+                (n_class, n_SV))
 
     def predict(self, X):
         """Perform regression on samples in X.



######## ITEM 3-25: scikit-learn__scikit-learn-25973 (gemma26 s0)
=== GOLD PATCH
diff --git a/sklearn/feature_selection/_sequential.py b/sklearn/feature_selection/_sequential.py
--- a/sklearn/feature_selection/_sequential.py
+++ b/sklearn/feature_selection/_sequential.py
@@ -8,12 +8,12 @@
 import warnings
 
 from ._base import SelectorMixin
-from ..base import BaseEstimator, MetaEstimatorMixin, clone
+from ..base import BaseEstimator, MetaEstimatorMixin, clone, is_classifier
 from ..utils._param_validation import HasMethods, Hidden, Interval, StrOptions
 from ..utils._param_validation import RealNotInt
 from ..utils._tags import _safe_tags
 from ..utils.validation import check_is_fitted
-from ..model_selection import cross_val_score
+from ..model_selection import cross_val_score, check_cv
 from ..metrics import get_scorer_names
 
 
@@ -259,6 +259,8 @@ def fit(self, X, y=None):
         if self.tol is not None and self.tol < 0 and self.direction == "forward":
             raise ValueError("tol must be positive when doing forward selection")
 
+        cv = check_cv(self.cv, y, classifier=is_classifier(self.estimator))
+
         cloned_estimator = clone(self.estimator)
 
         # the current mask corresponds to the set of features:
@@ -275,7 +277,7 @@ def fit(self, X, y=None):
         is_auto_select = self.tol is not None and self.n_features_to_select == "auto"
         for _ in range(n_iterations):
             new_feature_idx, new_score = self._get_best_new_feature_score(
-                cloned_estimator, X, y, current_mask
+                cloned_estimator, X, y, cv, current_mask
             )
             if is_auto_select and ((new_score - old_score) < self.tol):
                 break
@@ -291,7 +293,7 @@ def fit(self, X, y=None):
 
         return self
 
-    def _get_best_new_feature_score(self, estimator, X, y, current_mask):
+    def _get_best_new_feature_score(self, estimator, X, y, cv, current_mask):
         # Return the best new feature and its score to add to the current_mask,
         # i.e. return the best new feature and its score to add (resp. remove)
         # when doing forward selection (resp. backward selection).
@@ -309,7 +311,7 @@ def _get_best_new_feature_score(self, estimator, X, y, current_mask):
                 estimator,
                 X_new,
                 y,
-                cv=self.cv,
+                cv=cv,
                 scoring=self.scoring,
                 n_jobs=self.n_jobs,
             ).mean()

=== CANDIDATE PATCH
diff --git a/sklearn/feature_selection/_sequential.py b/sklearn/feature_selection/_sequential.py
--- a/sklearn/feature_selection/_sequential.py
+++ b/sklearn/feature_selection/_sequential.py
@@ -261,6 +261,9 @@
 
         cloned_estimator = clone(self.estimator)
 
+        if self.cv is not None and hasattr(self.cv, "__next__"):
+            self.cv = list(self.cv)
+
         # the current mask corresponds to the set of features:
         # - that we have already *selected* if we do forward selection
         # - that we have already *excluded* if we do backward selection
@@ -273,6 +276,20 @@
 
         old_score = -np.inf
         is_auto_select = self.tol is not None and self.n_features_to_select == "auto"
+
+        if self.cv is not None and not isinstance(self.cv, (int, type(None))):
+            try:
+                iter(self.cv)
+                # If it is an iterator but not a list/tuple/etc, convert to list
+                # to allow multiple passes over the splits.
+                if not isinstance(self.cv, (list, tuple)):
+                    # Check if it's a generator/iterator by trying to peek or 
+                    # just check if it has __next__
+                    if hasattr(self.cv, "__next__"):
+                        self.cv = list(self.cv)
+            except TypeError:
+                pass
+
         for _ in range(n_iterations):
             new_feature_idx, new_score = self._get_best_new_feature_score(
                 cloned_estimator, X, y, current_mask



######## ITEM 3-26: scikit-learn__scikit-learn-25973 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/sklearn/feature_selection/_sequential.py b/sklearn/feature_selection/_sequential.py
--- a/sklearn/feature_selection/_sequential.py
+++ b/sklearn/feature_selection/_sequential.py
@@ -8,12 +8,12 @@
 import warnings
 
 from ._base import SelectorMixin
-from ..base import BaseEstimator, MetaEstimatorMixin, clone
+from ..base import BaseEstimator, MetaEstimatorMixin, clone, is_classifier
 from ..utils._param_validation import HasMethods, Hidden, Interval, StrOptions
 from ..utils._param_validation import RealNotInt
 from ..utils._tags import _safe_tags
 from ..utils.validation import check_is_fitted
-from ..model_selection import cross_val_score
+from ..model_selection import cross_val_score, check_cv
 from ..metrics import get_scorer_names
 
 
@@ -259,6 +259,8 @@ def fit(self, X, y=None):
         if self.tol is not None and self.tol < 0 and self.direction == "forward":
             raise ValueError("tol must be positive when doing forward selection")
 
+        cv = check_cv(self.cv, y, classifier=is_classifier(self.estimator))
+
         cloned_estimator = clone(self.estimator)
 
         # the current mask corresponds to the set of features:
@@ -275,7 +277,7 @@ def fit(self, X, y=None):
         is_auto_select = self.tol is not None and self.n_features_to_select == "auto"
         for _ in range(n_iterations):
             new_feature_idx, new_score = self._get_best_new_feature_score(
-                cloned_estimator, X, y, current_mask
+                cloned_estimator, X, y, cv, current_mask
             )
             if is_auto_select and ((new_score - old_score) < self.tol):
                 break
@@ -291,7 +293,7 @@ def fit(self, X, y=None):
 
         return self
 
-    def _get_best_new_feature_score(self, estimator, X, y, current_mask):
+    def _get_best_new_feature_score(self, estimator, X, y, cv, current_mask):
         # Return the best new feature and its score to add to the current_mask,
         # i.e. return the best new feature and its score to add (resp. remove)
         # when doing forward selection (resp. backward selection).
@@ -309,7 +311,7 @@ def _get_best_new_feature_score(self, estimator, X, y, current_mask):
                 estimator,
                 X_new,
                 y,
-                cv=self.cv,
+                cv=cv,
                 scoring=self.scoring,
                 n_jobs=self.n_jobs,
             ).mean()

=== CANDIDATE PATCH
diff --git a/sklearn/feature_selection/_sequential.py b/sklearn/feature_selection/_sequential.py
--- a/sklearn/feature_selection/_sequential.py
+++ b/sklearn/feature_selection/_sequential.py
@@ -205,6 +205,10 @@
             Returns the instance itself.
         """
         self._validate_params()
+        # Materialize iterable cv (e.g., generator of splits) to a list
+        # to avoid exhaustion across multiple cross_val_score calls.
+        if not isinstance(self.cv, (int, )) and not hasattr(self.cv, "split"):
+            self.cv = list(self.cv)
 
         # FIXME: to be removed in 1.3
         if self.n_features_to_select in ("warn", None):



######## ITEM 3-27: scikit-learn__scikit-learn-25973 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/sklearn/feature_selection/_sequential.py b/sklearn/feature_selection/_sequential.py
--- a/sklearn/feature_selection/_sequential.py
+++ b/sklearn/feature_selection/_sequential.py
@@ -8,12 +8,12 @@
 import warnings
 
 from ._base import SelectorMixin
-from ..base import BaseEstimator, MetaEstimatorMixin, clone
+from ..base import BaseEstimator, MetaEstimatorMixin, clone, is_classifier
 from ..utils._param_validation import HasMethods, Hidden, Interval, StrOptions
 from ..utils._param_validation import RealNotInt
 from ..utils._tags import _safe_tags
 from ..utils.validation import check_is_fitted
-from ..model_selection import cross_val_score
+from ..model_selection import cross_val_score, check_cv
 from ..metrics import get_scorer_names
 
 
@@ -259,6 +259,8 @@ def fit(self, X, y=None):
         if self.tol is not None and self.tol < 0 and self.direction == "forward":
             raise ValueError("tol must be positive when doing forward selection")
 
+        cv = check_cv(self.cv, y, classifier=is_classifier(self.estimator))
+
         cloned_estimator = clone(self.estimator)
 
         # the current mask corresponds to the set of features:
@@ -275,7 +277,7 @@ def fit(self, X, y=None):
         is_auto_select = self.tol is not None and self.n_features_to_select == "auto"
         for _ in range(n_iterations):
             new_feature_idx, new_score = self._get_best_new_feature_score(
-                cloned_estimator, X, y, current_mask
+                cloned_estimator, X, y, cv, current_mask
             )
             if is_auto_select and ((new_score - old_score) < self.tol):
                 break
@@ -291,7 +293,7 @@ def fit(self, X, y=None):
 
         return self
 
-    def _get_best_new_feature_score(self, estimator, X, y, current_mask):
+    def _get_best_new_feature_score(self, estimator, X, y, cv, current_mask):
         # Return the best new feature and its score to add to the current_mask,
         # i.e. return the best new feature and its score to add (resp. remove)
         # when doing forward selection (resp. backward selection).
@@ -309,7 +311,7 @@ def _get_best_new_feature_score(self, estimator, X, y, current_mask):
                 estimator,
                 X_new,
                 y,
-                cv=self.cv,
+                cv=cv,
                 scoring=self.scoring,
                 n_jobs=self.n_jobs,
             ).mean()

=== CANDIDATE PATCH
diff --git a/sklearn/feature_selection/_sequential.py b/sklearn/feature_selection/_sequential.py
--- a/sklearn/feature_selection/_sequential.py
+++ b/sklearn/feature_selection/_sequential.py
@@ -228,6 +228,12 @@
             force_all_finite=not tags.get("allow_nan", True),
         )
         n_features = X.shape[1]
+        # Ensure cv is reusable when provided as an iterator
+        if not hasattr(self.cv, "get_n_splits"):
+            try:
+                self.cv = list(self.cv)
+            except TypeError:
+                pass
 
         # FIXME: to be fixed in 1.3
         error_msg = (



######## ITEM 3-28: scikit-learn__scikit-learn-25973 (gpt-oss-20b s2)
=== GOLD PATCH
diff --git a/sklearn/feature_selection/_sequential.py b/sklearn/feature_selection/_sequential.py
--- a/sklearn/feature_selection/_sequential.py
+++ b/sklearn/feature_selection/_sequential.py
@@ -8,12 +8,12 @@
 import warnings
 
 from ._base import SelectorMixin
-from ..base import BaseEstimator, MetaEstimatorMixin, clone
+from ..base import BaseEstimator, MetaEstimatorMixin, clone, is_classifier
 from ..utils._param_validation import HasMethods, Hidden, Interval, StrOptions
 from ..utils._param_validation import RealNotInt
 from ..utils._tags import _safe_tags
 from ..utils.validation import check_is_fitted
-from ..model_selection import cross_val_score
+from ..model_selection import cross_val_score, check_cv
 from ..metrics import get_scorer_names
 
 
@@ -259,6 +259,8 @@ def fit(self, X, y=None):
         if self.tol is not None and self.tol < 0 and self.direction == "forward":
             raise ValueError("tol must be positive when doing forward selection")
 
+        cv = check_cv(self.cv, y, classifier=is_classifier(self.estimator))
+
         cloned_estimator = clone(self.estimator)
 
         # the current mask corresponds to the set of features:
@@ -275,7 +277,7 @@ def fit(self, X, y=None):
         is_auto_select = self.tol is not None and self.n_features_to_select == "auto"
         for _ in range(n_iterations):
             new_feature_idx, new_score = self._get_best_new_feature_score(
-                cloned_estimator, X, y, current_mask
+                cloned_estimator, X, y, cv, current_mask
             )
             if is_auto_select and ((new_score - old_score) < self.tol):
                 break
@@ -291,7 +293,7 @@ def fit(self, X, y=None):
 
         return self
 
-    def _get_best_new_feature_score(self, estimator, X, y, current_mask):
+    def _get_best_new_feature_score(self, estimator, X, y, cv, current_mask):
         # Return the best new feature and its score to add to the current_mask,
         # i.e. return the best new feature and its score to add (resp. remove)
         # when doing forward selection (resp. backward selection).
@@ -309,7 +311,7 @@ def _get_best_new_feature_score(self, estimator, X, y, current_mask):
                 estimator,
                 X_new,
                 y,
-                cv=self.cv,
+                cv=cv,
                 scoring=self.scoring,
                 n_jobs=self.n_jobs,
             ).mean()

=== CANDIDATE PATCH
diff --git a/sklearn/feature_selection/_sequential.py b/sklearn/feature_selection/_sequential.py
--- a/sklearn/feature_selection/_sequential.py
+++ b/sklearn/feature_selection/_sequential.py
@@ -205,6 +205,19 @@
             Returns the instance itself.
         """
         self._validate_params()
+        # materialise iterable cv objects to allow reuse across folds
+        # `cv` may be an integer, a CV splitter, or an iterable of splits.
+        # For integer values, or CV splitters (`hasattr(cv, "split")`),
+        # we leave it untouched.  For iterables (e.g., generators from
+        # LeaveOneGroupOut.split), we convert them to a list so that the
+        # same splits can be reused on each call to `cross_val_score`.
+        if not isinstance(self.cv, Integral) and not hasattr(self.cv, "split"):
+            try:
+                self.cv = list(self.cv)
+            except Exception as exc:
+                raise ValueError(
+                    "cv is not a valid CV splitter or iterable of splits"
+                ) from exc
 
         # FIXME: to be removed in 1.3
         if self.n_features_to_select in ("warn", None):



######## ITEM 3-29: sphinx-doc__sphinx-10466 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/sphinx/builders/gettext.py b/sphinx/builders/gettext.py
--- a/sphinx/builders/gettext.py
+++ b/sphinx/builders/gettext.py
@@ -57,7 +57,8 @@ def add(self, msg: str, origin: Union[Element, "MsgOrigin"]) -> None:
 
     def __iter__(self) -> Generator[Message, None, None]:
         for message in self.messages:
-            positions = [(source, line) for source, line, uuid in self.metadata[message]]
+            positions = sorted(set((source, line) for source, line, uuid
+                                   in self.metadata[message]))
             uuids = [uuid for source, line, uuid in self.metadata[message]]
             yield Message(message, positions, uuids)
 

=== CANDIDATE PATCH
diff --git a/sphinx/builders/gettext.py b/sphinx/builders/gettext.py
--- a/sphinx/builders/gettext.py
+++ b/sphinx/builders/gettext.py
@@ -32,8 +32,18 @@
     """An entry of translatable message."""
     def __init__(self, text: str, locations: List[Tuple[str, int]], uuids: List[str]):
         self.text = text
-        self.locations = locations
-        self.uuids = uuids
+        # Remove duplicate locations while preserving order.
+        # Keep the first UUID associated with each unique location.
+        seen: set = set()
+        uniq_locations: List[Tuple[str, int]] = []
+        uniq_uuids: List[str] = []
+        for loc, uid in zip(locations, uuids):
+            if loc not in seen:
+                seen.add(loc)
+                uniq_locations.append(loc)
+                uniq_uuids.append(uid)
+        self.locations = uniq_locations
+        self.uuids = uniq_uuids
 
 
 class Catalog:



######## ITEM 3-30: sphinx-doc__sphinx-10466 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/sphinx/builders/gettext.py b/sphinx/builders/gettext.py
--- a/sphinx/builders/gettext.py
+++ b/sphinx/builders/gettext.py
@@ -57,7 +57,8 @@ def add(self, msg: str, origin: Union[Element, "MsgOrigin"]) -> None:
 
     def __iter__(self) -> Generator[Message, None, None]:
         for message in self.messages:
-            positions = [(source, line) for source, line, uuid in self.metadata[message]]
+            positions = sorted(set((source, line) for source, line, uuid
+                                   in self.metadata[message]))
             uuids = [uuid for source, line, uuid in self.metadata[message]]
             yield Message(message, positions, uuids)
 

=== CANDIDATE PATCH
diff --git a/sphinx/builders/gettext.py b/sphinx/builders/gettext.py
--- a/sphinx/builders/gettext.py
+++ b/sphinx/builders/gettext.py
@@ -32,8 +32,19 @@
     """An entry of translatable message."""
     def __init__(self, text: str, locations: List[Tuple[str, int]], uuids: List[str]):
         self.text = text
-        self.locations = locations
-        self.uuids = uuids
+        # Deduplicate locations while preserving order.
+        # Each location is a (source, line) tuple; duplicate entries can occur
+        # because different UUIDs are generated for the same source line.
+        seen: Set[Tuple[str, int]] = set()
+        uniq_locations: List[Tuple[str, int]] = []
+        uniq_uuids: List[str] = []
+        for loc, uid in zip(locations, uuids):
+            if loc not in seen:
+                seen.add(loc)
+                uniq_locations.append(loc)
+                uniq_uuids.append(uid)
+        self.locations = uniq_locations
+        self.uuids = uniq_uuids
 
 
 class Catalog:



######## ITEM 3-31: sphinx-doc__sphinx-10466 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/sphinx/builders/gettext.py b/sphinx/builders/gettext.py
--- a/sphinx/builders/gettext.py
+++ b/sphinx/builders/gettext.py
@@ -57,7 +57,8 @@ def add(self, msg: str, origin: Union[Element, "MsgOrigin"]) -> None:
 
     def __iter__(self) -> Generator[Message, None, None]:
         for message in self.messages:
-            positions = [(source, line) for source, line, uuid in self.metadata[message]]
+            positions = sorted(set((source, line) for source, line, uuid
+                                   in self.metadata[message]))
             uuids = [uuid for source, line, uuid in self.metadata[message]]
             yield Message(message, positions, uuids)
 

=== CANDIDATE PATCH
diff --git a/sphinx/builders/gettext.py b/sphinx/builders/gettext.py
--- a/sphinx/builders/gettext.py
+++ b/sphinx/builders/gettext.py
@@ -32,8 +32,18 @@
     """An entry of translatable message."""
     def __init__(self, text: str, locations: List[Tuple[str, int]], uuids: List[str]):
         self.text = text
-        self.locations = locations
-        self.uuids = uuids
+        # Deduplicate locations while preserving order.
+        # ``uuids`` correspond one‑to‑one with ``locations``; keep the first uuid for each unique location.
+        seen: Set[Tuple[str, int]] = set()
+        uniq_locations: List[Tuple[str, int]] = []
+        uniq_uuids: List[str] = []
+        for loc, uid in zip(locations, uuids):
+            if loc not in seen:
+                seen.add(loc)
+                uniq_locations.append(loc)
+                uniq_uuids.append(uid)
+        self.locations = uniq_locations
+        self.uuids = uniq_uuids
 
 
 class Catalog:



######## ITEM 3-32: sphinx-doc__sphinx-10466 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/sphinx/builders/gettext.py b/sphinx/builders/gettext.py
--- a/sphinx/builders/gettext.py
+++ b/sphinx/builders/gettext.py
@@ -57,7 +57,8 @@ def add(self, msg: str, origin: Union[Element, "MsgOrigin"]) -> None:
 
     def __iter__(self) -> Generator[Message, None, None]:
         for message in self.messages:
-            positions = [(source, line) for source, line, uuid in self.metadata[message]]
+            positions = sorted(set((source, line) for source, line, uuid
+                                   in self.metadata[message]))
             uuids = [uuid for source, line, uuid in self.metadata[message]]
             yield Message(message, positions, uuids)
 

=== CANDIDATE PATCH
diff --git a/sphinx/builders/gettext.py b/sphinx/builders/gettext.py
--- a/sphinx/builders/gettext.py
+++ b/sphinx/builders/gettext.py
@@ -59,6 +59,9 @@
         for message in self.messages:
             positions = [(source, line) for source, line, uuid in self.metadata[message]]
             uuids = [uuid for source, line, uuid in self.metadata[message]]
+            # Remove duplicate locations while preserving order
+            positions = list(dict.fromkeys(positions))
+            uuids = list(dict.fromkeys(uuids))
             yield Message(message, positions, uuids)
 
 



######## ITEM 3-33: sphinx-doc__sphinx-10466 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/sphinx/builders/gettext.py b/sphinx/builders/gettext.py
--- a/sphinx/builders/gettext.py
+++ b/sphinx/builders/gettext.py
@@ -57,7 +57,8 @@ def add(self, msg: str, origin: Union[Element, "MsgOrigin"]) -> None:
 
     def __iter__(self) -> Generator[Message, None, None]:
         for message in self.messages:
-            positions = [(source, line) for source, line, uuid in self.metadata[message]]
+            positions = sorted(set((source, line) for source, line, uuid
+                                   in self.metadata[message]))
             uuids = [uuid for source, line, uuid in self.metadata[message]]
             yield Message(message, positions, uuids)
 

=== CANDIDATE PATCH
diff --git a/sphinx/builders/gettext.py b/sphinx/builders/gettext.py
--- a/sphinx/builders/gettext.py
+++ b/sphinx/builders/gettext.py
@@ -32,7 +32,8 @@
     """An entry of translatable message."""
     def __init__(self, text: str, locations: List[Tuple[str, int]], uuids: List[str]):
         self.text = text
-        self.locations = locations
+        # Preserve order while deduplicating location tuples
+        self.locations = list(dict.fromkeys(locations))
         self.uuids = uuids
 
 



######## ITEM 3-34: sphinx-doc__sphinx-10466 (gpt-oss-20b s2)
=== GOLD PATCH
diff --git a/sphinx/builders/gettext.py b/sphinx/builders/gettext.py
--- a/sphinx/builders/gettext.py
+++ b/sphinx/builders/gettext.py
@@ -57,7 +57,8 @@ def add(self, msg: str, origin: Union[Element, "MsgOrigin"]) -> None:
 
     def __iter__(self) -> Generator[Message, None, None]:
         for message in self.messages:
-            positions = [(source, line) for source, line, uuid in self.metadata[message]]
+            positions = sorted(set((source, line) for source, line, uuid
+                                   in self.metadata[message]))
             uuids = [uuid for source, line, uuid in self.metadata[message]]
             yield Message(message, positions, uuids)
 

=== CANDIDATE PATCH
diff --git a/sphinx/builders/gettext.py b/sphinx/builders/gettext.py
--- a/sphinx/builders/gettext.py
+++ b/sphinx/builders/gettext.py
@@ -59,7 +59,15 @@
         for message in self.messages:
             positions = [(source, line) for source, line, uuid in self.metadata[message]]
             uuids = [uuid for source, line, uuid in self.metadata[message]]
-            yield Message(message, positions, uuids)
+            seen: Set[Tuple[str, int]] = set()
+            unique_positions: List[Tuple[str, int]] = []
+            unique_uuids: List[str] = []
+            for pos, uid in zip(positions, uuids):
+                if pos not in seen:
+                    seen.add(pos)
+                    unique_positions.append(pos)
+                    unique_uuids.append(uid)
+            yield Message(message, unique_positions, unique_uuids)
 
 
 class MsgOrigin:



######## ITEM 3-35: sphinx-doc__sphinx-11445 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/sphinx/util/rst.py b/sphinx/util/rst.py
--- a/sphinx/util/rst.py
+++ b/sphinx/util/rst.py
@@ -10,22 +10,17 @@
 
 from docutils.parsers.rst import roles
 from docutils.parsers.rst.languages import en as english
+from docutils.parsers.rst.states import Body
 from docutils.statemachine import StringList
 from docutils.utils import Reporter
-from jinja2 import Environment
+from jinja2 import Environment, pass_environment
 
 from sphinx.locale import __
 from sphinx.util import docutils, logging
 
-try:
-    from jinja2.utils import pass_environment
-except ImportError:
-    from jinja2 import environmentfilter as pass_environment
-
-
 logger = logging.getLogger(__name__)
 
-docinfo_re = re.compile(':\\w+:.*?')
+FIELD_NAME_RE = re.compile(Body.patterns['field_marker'])
 symbols_re = re.compile(r'([!-\-/:-@\[-`{-~])')  # symbols without dot(0x2e)
 SECTIONING_CHARS = ['=', '-', '~']
 
@@ -80,7 +75,7 @@ def prepend_prolog(content: StringList, prolog: str) -> None:
     if prolog:
         pos = 0
         for line in content:
-            if docinfo_re.match(line):
+            if FIELD_NAME_RE.match(line):
                 pos += 1
             else:
                 break
@@ -91,6 +86,7 @@ def prepend_prolog(content: StringList, prolog: str) -> None:
             pos += 1
 
         # insert prolog (after docinfo if exists)
+        lineno = 0
         for lineno, line in enumerate(prolog.splitlines()):
             content.insert(pos + lineno, line, '<rst_prolog>', lineno)
 

=== CANDIDATE PATCH
diff --git a/sphinx/util/rst.py b/sphinx/util/rst.py
--- a/sphinx/util/rst.py
+++ b/sphinx/util/rst.py
@@ -25,7 +25,7 @@
 
 logger = logging.getLogger(__name__)
 
-docinfo_re = re.compile(':\\w+:.*?')
+docinfo_re = re.compile(r':\w+:\s')
 symbols_re = re.compile(r'([!-\-/:-@\[-`{-~])')  # symbols without dot(0x2e)
 SECTIONING_CHARS = ['=', '-', '~']
 



######## ITEM 3-36: sphinx-doc__sphinx-11445 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/sphinx/util/rst.py b/sphinx/util/rst.py
--- a/sphinx/util/rst.py
+++ b/sphinx/util/rst.py
@@ -10,22 +10,17 @@
 
 from docutils.parsers.rst import roles
 from docutils.parsers.rst.languages import en as english
+from docutils.parsers.rst.states import Body
 from docutils.statemachine import StringList
 from docutils.utils import Reporter
-from jinja2 import Environment
+from jinja2 import Environment, pass_environment
 
 from sphinx.locale import __
 from sphinx.util import docutils, logging
 
-try:
-    from jinja2.utils import pass_environment
-except ImportError:
-    from jinja2 import environmentfilter as pass_environment
-
-
 logger = logging.getLogger(__name__)
 
-docinfo_re = re.compile(':\\w+:.*?')
+FIELD_NAME_RE = re.compile(Body.patterns['field_marker'])
 symbols_re = re.compile(r'([!-\-/:-@\[-`{-~])')  # symbols without dot(0x2e)
 SECTIONING_CHARS = ['=', '-', '~']
 
@@ -80,7 +75,7 @@ def prepend_prolog(content: StringList, prolog: str) -> None:
     if prolog:
         pos = 0
         for line in content:
-            if docinfo_re.match(line):
+            if FIELD_NAME_RE.match(line):
                 pos += 1
             else:
                 break
@@ -91,6 +86,7 @@ def prepend_prolog(content: StringList, prolog: str) -> None:
             pos += 1
 
         # insert prolog (after docinfo if exists)
+        lineno = 0
         for lineno, line in enumerate(prolog.splitlines()):
             content.insert(pos + lineno, line, '<rst_prolog>', lineno)
 

=== CANDIDATE PATCH
diff --git a/sphinx/util/rst.py b/sphinx/util/rst.py
--- a/sphinx/util/rst.py
+++ b/sphinx/util/rst.py
@@ -25,7 +25,7 @@
 
 logger = logging.getLogger(__name__)
 
-docinfo_re = re.compile(':\\w+:.*?')
+docinfo_re = re.compile(':\\w+:\\s.*?')
 symbols_re = re.compile(r'([!-\-/:-@\[-`{-~])')  # symbols without dot(0x2e)
 SECTIONING_CHARS = ['=', '-', '~']
 



######## ITEM 3-37: sphinx-doc__sphinx-11445 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/sphinx/util/rst.py b/sphinx/util/rst.py
--- a/sphinx/util/rst.py
+++ b/sphinx/util/rst.py
@@ -10,22 +10,17 @@
 
 from docutils.parsers.rst import roles
 from docutils.parsers.rst.languages import en as english
+from docutils.parsers.rst.states import Body
 from docutils.statemachine import StringList
 from docutils.utils import Reporter
-from jinja2 import Environment
+from jinja2 import Environment, pass_environment
 
 from sphinx.locale import __
 from sphinx.util import docutils, logging
 
-try:
-    from jinja2.utils import pass_environment
-except ImportError:
-    from jinja2 import environmentfilter as pass_environment
-
-
 logger = logging.getLogger(__name__)
 
-docinfo_re = re.compile(':\\w+:.*?')
+FIELD_NAME_RE = re.compile(Body.patterns['field_marker'])
 symbols_re = re.compile(r'([!-\-/:-@\[-`{-~])')  # symbols without dot(0x2e)
 SECTIONING_CHARS = ['=', '-', '~']
 
@@ -80,7 +75,7 @@ def prepend_prolog(content: StringList, prolog: str) -> None:
     if prolog:
         pos = 0
         for line in content:
-            if docinfo_re.match(line):
+            if FIELD_NAME_RE.match(line):
                 pos += 1
             else:
                 break
@@ -91,6 +86,7 @@ def prepend_prolog(content: StringList, prolog: str) -> None:
             pos += 1
 
         # insert prolog (after docinfo if exists)
+        lineno = 0
         for lineno, line in enumerate(prolog.splitlines()):
             content.insert(pos + lineno, line, '<rst_prolog>', lineno)
 

=== CANDIDATE PATCH
diff --git a/sphinx/util/rst.py b/sphinx/util/rst.py
--- a/sphinx/util/rst.py
+++ b/sphinx/util/rst.py
@@ -25,7 +25,7 @@
 
 logger = logging.getLogger(__name__)
 
-docinfo_re = re.compile(':\\w+:.*?')
+docinfo_re = re.compile('^:\\w+:\\s+.*$')
 symbols_re = re.compile(r'([!-\-/:-@\[-`{-~])')  # symbols without dot(0x2e)
 SECTIONING_CHARS = ['=', '-', '~']
 



######## ITEM 3-38: sphinx-doc__sphinx-9281 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/sphinx/util/inspect.py b/sphinx/util/inspect.py
--- a/sphinx/util/inspect.py
+++ b/sphinx/util/inspect.py
@@ -442,14 +442,14 @@ def object_description(object: Any) -> str:
                      (object_description(key), object_description(object[key]))
                      for key in sorted_keys)
             return "{%s}" % ", ".join(items)
-    if isinstance(object, set):
+    elif isinstance(object, set):
         try:
             sorted_values = sorted(object)
         except TypeError:
             pass  # Cannot sort set values, fall back to generic repr
         else:
             return "{%s}" % ", ".join(object_description(x) for x in sorted_values)
-    if isinstance(object, frozenset):
+    elif isinstance(object, frozenset):
         try:
             sorted_values = sorted(object)
         except TypeError:
@@ -457,6 +457,9 @@ def object_description(object: Any) -> str:
         else:
             return "frozenset({%s})" % ", ".join(object_description(x)
                                                  for x in sorted_values)
+    elif isinstance(object, enum.Enum):
+        return "%s.%s" % (object.__class__.__name__, object.name)
+
     try:
         s = repr(object)
     except Exception as exc:

=== CANDIDATE PATCH
diff --git a/sphinx/util/inspect.py b/sphinx/util/inspect.py
--- a/sphinx/util/inspect.py
+++ b/sphinx/util/inspect.py
@@ -457,6 +457,9 @@
         else:
             return "frozenset({%s})" % ", ".join(object_description(x)
                                                  for x in sorted_values)
+    # Special handling for Enum members to avoid the default ``<Enum.Member: value>`` format
+    if isinstance(object, enum.Enum):
+        return f"{object.__class__.__name__}.{object.name}"
     try:
         s = repr(object)
     except Exception as exc:



######## ITEM 3-39: sphinx-doc__sphinx-9711 (gemma26 s0)
=== GOLD PATCH
diff --git a/sphinx/extension.py b/sphinx/extension.py
--- a/sphinx/extension.py
+++ b/sphinx/extension.py
@@ -10,6 +10,8 @@
 
 from typing import TYPE_CHECKING, Any, Dict
 
+from packaging.version import InvalidVersion, Version
+
 from sphinx.config import Config
 from sphinx.errors import VersionRequirementError
 from sphinx.locale import __
@@ -51,7 +53,18 @@ def verify_needs_extensions(app: "Sphinx", config: Config) -> None:
                               'but it is not loaded.'), extname)
             continue
 
-        if extension.version == 'unknown version' or reqversion > extension.version:
+        fulfilled = True
+        if extension.version == 'unknown version':
+            fulfilled = False
+        else:
+            try:
+                if Version(reqversion) > Version(extension.version):
+                    fulfilled = False
+            except InvalidVersion:
+                if reqversion > extension.version:
+                    fulfilled = False
+
+        if not fulfilled:
             raise VersionRequirementError(__('This project needs the extension %s at least in '
                                              'version %s and therefore cannot be built with '
                                              'the loaded version (%s).') %

=== CANDIDATE PATCH
diff --git a/sphinx/extension.py b/sphinx/extension.py
--- a/sphinx/extension.py
+++ b/sphinx/extension.py
@@ -9,6 +9,8 @@
 """
 
 from typing import TYPE_CHECKING, Any, Dict
+
+from packaging import version
 
 from sphinx.config import Config
 from sphinx.errors import VersionRequirementError
@@ -51,11 +53,18 @@
                               'but it is not loaded.'), extname)
             continue
 
-        if extension.version == 'unknown version' or reqversion > extension.version:
-            raise VersionRequirementError(__('This project needs the extension %s at least in '
-                                             'version %s and therefore cannot be built with '
-                                             'the loaded version (%s).') %
-                                          (extname, reqversion, extension.version))
+        try:
+            if extension.version == 'unknown version' or version.parse(reqversion) > version.parse(extension.version):
+                raise VersionRequirementError(__('This project needs the extension %s at least in '
+                                                     'version %s and therefore cannot be built with '
+                                                     'the loaded version (%s).') %
+                                                      (extname, reqversion, extension.version))
+        except version.InvalidVersion:
+            if extension.version == 'unknown version' or reqversion > extension.version:
+                raise VersionRequirementError(__('This project needs the extension %s at least in '
+                                                     'version %s and therefore cannot be built with '
+                                                     'the loaded version (%s).') %
+                                                      (extname, reqversion, extension.version))
 
 
 def setup(app: "Sphinx") -> Dict[str, Any]:



######## ITEM 3-40: sphinx-doc__sphinx-9711 (gemma26 s1)
=== GOLD PATCH
diff --git a/sphinx/extension.py b/sphinx/extension.py
--- a/sphinx/extension.py
+++ b/sphinx/extension.py
@@ -10,6 +10,8 @@
 
 from typing import TYPE_CHECKING, Any, Dict
 
+from packaging.version import InvalidVersion, Version
+
 from sphinx.config import Config
 from sphinx.errors import VersionRequirementError
 from sphinx.locale import __
@@ -51,7 +53,18 @@ def verify_needs_extensions(app: "Sphinx", config: Config) -> None:
                               'but it is not loaded.'), extname)
             continue
 
-        if extension.version == 'unknown version' or reqversion > extension.version:
+        fulfilled = True
+        if extension.version == 'unknown version':
+            fulfilled = False
+        else:
+            try:
+                if Version(reqversion) > Version(extension.version):
+                    fulfilled = False
+            except InvalidVersion:
+                if reqversion > extension.version:
+                    fulfilled = False
+
+        if not fulfilled:
             raise VersionRequirementError(__('This project needs the extension %s at least in '
                                              'version %s and therefore cannot be built with '
                                              'the loaded version (%s).') %

=== CANDIDATE PATCH
diff --git a/sphinx/extension.py b/sphinx/extension.py
--- a/sphinx/extension.py
+++ b/sphinx/extension.py
@@ -9,6 +9,8 @@
 """
 
 from typing import TYPE_CHECKING, Any, Dict
+
+from packaging import version
 
 from sphinx.config import Config
 from sphinx.errors import VersionRequirementError
@@ -51,11 +53,18 @@
                               'but it is not loaded.'), extname)
             continue
 
-        if extension.version == 'unknown version' or reqversion > extension.version:
-            raise VersionRequirementError(__('This project needs the extension %s at least in '
-                                             'version %s and therefore cannot be built with '
-                                             'the loaded version (%s).') %
-                                          (extname, reqversion, extension.version))
+        try:
+            if extension.version == 'unknown version' or version.parse(reqversion) > version.parse(extension.version):
+                raise VersionRequirementError(__('This project needs the extension %s at least in '
+                                                     'version %s and therefore cannot be built with '
+                                                     'the loaded version (%s).') %
+                                                  (extname, reqversion, extension.version))
+        except version.InvalidVersion:
+            if extension.version == 'unknown version' or reqversion > extension.version:
+                raise VersionRequirementError(__('This project needs the extension %s at least in '
+                                                     'version %s and therefore cannot be built with '
+                                                     'the loaded version (%s).') %
+                                                  (extname, reqversion, extension.version))
 
 
 def setup(app: "Sphinx") -> Dict[str, Any]:



######## ITEM 3-41: sphinx-doc__sphinx-9711 (gemma26 s2)
=== GOLD PATCH
diff --git a/sphinx/extension.py b/sphinx/extension.py
--- a/sphinx/extension.py
+++ b/sphinx/extension.py
@@ -10,6 +10,8 @@
 
 from typing import TYPE_CHECKING, Any, Dict
 
+from packaging.version import InvalidVersion, Version
+
 from sphinx.config import Config
 from sphinx.errors import VersionRequirementError
 from sphinx.locale import __
@@ -51,7 +53,18 @@ def verify_needs_extensions(app: "Sphinx", config: Config) -> None:
                               'but it is not loaded.'), extname)
             continue
 
-        if extension.version == 'unknown version' or reqversion > extension.version:
+        fulfilled = True
+        if extension.version == 'unknown version':
+            fulfilled = False
+        else:
+            try:
+                if Version(reqversion) > Version(extension.version):
+                    fulfilled = False
+            except InvalidVersion:
+                if reqversion > extension.version:
+                    fulfilled = False
+
+        if not fulfilled:
             raise VersionRequirementError(__('This project needs the extension %s at least in '
                                              'version %s and therefore cannot be built with '
                                              'the loaded version (%s).') %

=== CANDIDATE PATCH
diff --git a/sphinx/extension.py b/sphinx/extension.py
--- a/sphinx/extension.py
+++ b/sphinx/extension.py
@@ -9,6 +9,8 @@
 """
 
 from typing import TYPE_CHECKING, Any, Dict
+
+from packaging.version import parse as parse_version
 
 from sphinx.config import Config
 from sphinx.errors import VersionRequirementError
@@ -51,11 +53,19 @@
                               'but it is not loaded.'), extname)
             continue
 
-        if extension.version == 'unknown version' or reqversion > extension.version:
-            raise VersionRequirementError(__('This project needs the extension %s at least in '
-                                             'version %s and therefore cannot be built with '
-                                             'the loaded version (%s).') %
-                                          (extname, reqversion, extension.version))
+        try:
+            if extension.version == 'unknown version' or parse_version(extension.version) < parse_version(reqversion):
+                raise VersionRequirementError(__('This project needs the extension %s at least in '
+                                                     'version %s and therefore cannot be built with '
+                                                     'the loaded version (%s).') %
+                                                      (extname, reqversion, extension.version))
+        except Exception:
+            # If version parsing fails, fall back to string comparison
+            if extension.version == 'unknown version' or reqversion > extension.version:
+                raise VersionRequirementError(__('This project needs the extension %s at least in '
+                                                     'version %s and therefore cannot be built with '
+                                                     'the loaded version (%s).') %
+                                                      (extname, reqversion, extension.version))
 
 
 def setup(app: "Sphinx") -> Dict[str, Any]:



######## ITEM 3-42: sphinx-doc__sphinx-9711 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/sphinx/extension.py b/sphinx/extension.py
--- a/sphinx/extension.py
+++ b/sphinx/extension.py
@@ -10,6 +10,8 @@
 
 from typing import TYPE_CHECKING, Any, Dict
 
+from packaging.version import InvalidVersion, Version
+
 from sphinx.config import Config
 from sphinx.errors import VersionRequirementError
 from sphinx.locale import __
@@ -51,7 +53,18 @@ def verify_needs_extensions(app: "Sphinx", config: Config) -> None:
                               'but it is not loaded.'), extname)
             continue
 
-        if extension.version == 'unknown version' or reqversion > extension.version:
+        fulfilled = True
+        if extension.version == 'unknown version':
+            fulfilled = False
+        else:
+            try:
+                if Version(reqversion) > Version(extension.version):
+                    fulfilled = False
+            except InvalidVersion:
+                if reqversion > extension.version:
+                    fulfilled = False
+
+        if not fulfilled:
             raise VersionRequirementError(__('This project needs the extension %s at least in '
                                              'version %s and therefore cannot be built with '
                                              'the loaded version (%s).') %

=== CANDIDATE PATCH
diff --git a/sphinx/extension.py b/sphinx/extension.py
--- a/sphinx/extension.py
+++ b/sphinx/extension.py
@@ -14,6 +14,11 @@
 from sphinx.errors import VersionRequirementError
 from sphinx.locale import __
 from sphinx.util import logging
+# Version parsing utility (fallback to simple string comparison if unavailable)
+try:
+    from packaging.version import parse as parse_version
+except Exception:  # pragma: no cover
+    from distutils.version import LooseVersion as parse_version
 
 if TYPE_CHECKING:
     from sphinx.application import Sphinx
@@ -51,7 +56,8 @@
                               'but it is not loaded.'), extname)
             continue
 
-        if extension.version == 'unknown version' or reqversion > extension.version:
+        # Compare versions using proper parsing; fall back to string compare if parsing fails
+        if extension.version == 'unknown version' or parse_version(reqversion) > parse_version(extension.version):
             raise VersionRequirementError(__('This project needs the extension %s at least in '
                                              'version %s and therefore cannot be built with '
                                              'the loaded version (%s).') %



######## ITEM 3-43: sphinx-doc__sphinx-9711 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/sphinx/extension.py b/sphinx/extension.py
--- a/sphinx/extension.py
+++ b/sphinx/extension.py
@@ -10,6 +10,8 @@
 
 from typing import TYPE_CHECKING, Any, Dict
 
+from packaging.version import InvalidVersion, Version
+
 from sphinx.config import Config
 from sphinx.errors import VersionRequirementError
 from sphinx.locale import __
@@ -51,7 +53,18 @@ def verify_needs_extensions(app: "Sphinx", config: Config) -> None:
                               'but it is not loaded.'), extname)
             continue
 
-        if extension.version == 'unknown version' or reqversion > extension.version:
+        fulfilled = True
+        if extension.version == 'unknown version':
+            fulfilled = False
+        else:
+            try:
+                if Version(reqversion) > Version(extension.version):
+                    fulfilled = False
+            except InvalidVersion:
+                if reqversion > extension.version:
+                    fulfilled = False
+
+        if not fulfilled:
             raise VersionRequirementError(__('This project needs the extension %s at least in '
                                              'version %s and therefore cannot be built with '
                                              'the loaded version (%s).') %

=== CANDIDATE PATCH
diff --git a/sphinx/extension.py b/sphinx/extension.py
--- a/sphinx/extension.py
+++ b/sphinx/extension.py
@@ -14,6 +14,7 @@
 from sphinx.errors import VersionRequirementError
 from sphinx.locale import __
 from sphinx.util import logging
+from packaging.version import Version, InvalidVersion
 
 if TYPE_CHECKING:
     from sphinx.application import Sphinx
@@ -51,11 +52,25 @@
                               'but it is not loaded.'), extname)
             continue
 
-        if extension.version == 'unknown version' or reqversion > extension.version:
+        # Check version requirement using proper version parsing.
+        if extension.version == 'unknown version':
             raise VersionRequirementError(__('This project needs the extension %s at least in '
                                              'version %s and therefore cannot be built with '
                                              'the loaded version (%s).') %
                                           (extname, reqversion, extension.version))
+        try:
+            if Version(extension.version) < Version(reqversion):
+                raise VersionRequirementError(__('This project needs the extension %s at least in '
+                                                 'version %s and therefore cannot be built with '
+                                                 'the loaded version (%s).') %
+                                              (extname, reqversion, extension.version))
+        except InvalidVersion:
+            # Fallback to the original string comparison if parsing fails.
+            if reqversion > extension.version:
+                raise VersionRequirementError(__('This project needs the extension %s at least in '
+                                                 'version %s and therefore cannot be built with '
+                                                 'the loaded version (%s).') %
+                                              (extname, reqversion, extension.version))
 
 
 def setup(app: "Sphinx") -> Dict[str, Any]:

