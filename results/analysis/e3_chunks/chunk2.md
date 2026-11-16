

######## ITEM 2-0: matplotlib__matplotlib-24637 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1446,6 +1446,7 @@ def draw(self, renderer):
             self._renderer = renderer
         if not self.get_visible() or not self._check_xy(renderer):
             return
+        renderer.open_group(self.__class__.__name__, gid=self.get_gid())
         self.update_positions(renderer)
         if self.arrow_patch is not None:
             if self.arrow_patch.figure is None and self.figure is not None:
@@ -1453,6 +1454,7 @@ def draw(self, renderer):
             self.arrow_patch.draw(renderer)
         self.patch.draw(renderer)
         self.offsetbox.draw(renderer)
+        renderer.close_group(self.__class__.__name__)
         self.stale = False
 
 

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1453,6 +1453,19 @@
         if not self.get_visible() or not self._check_xy(renderer):
             return
         self.update_positions(renderer)
+        # Propagate gid to the drawn sub‑artists so that SVG output
+        # includes the gid for the image (and any other children).
+        gid = self.get_gid()
+        if gid:
+            # the surrounding patch (frame)
+            self.patch.set_gid(gid)
+            # the arrow, if present
+            if self.arrow_patch is not None:
+                self.arrow_patch.set_gid(gid)
+            # the offset box container and its children (e.g. the image)
+            self.offsetbox.set_gid(gid)
+            for child in self.offsetbox.get_children():
+                child.set_gid(gid)
         if self.arrow_patch is not None:
             if self.arrow_patch.figure is None and self.figure is not None:
                 self.arrow_patch.figure = self.figure



######## ITEM 2-1: matplotlib__matplotlib-24970 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/lib/matplotlib/colors.py b/lib/matplotlib/colors.py
--- a/lib/matplotlib/colors.py
+++ b/lib/matplotlib/colors.py
@@ -715,16 +715,17 @@ def __call__(self, X, alpha=None, bytes=False):
         if not xa.dtype.isnative:
             xa = xa.byteswap().newbyteorder()  # Native byteorder is faster.
         if xa.dtype.kind == "f":
-            with np.errstate(invalid="ignore"):
-                xa *= self.N
-                # Negative values are out of range, but astype(int) would
-                # truncate them towards zero.
-                xa[xa < 0] = -1
-                # xa == 1 (== N after multiplication) is not out of range.
-                xa[xa == self.N] = self.N - 1
-                # Avoid converting large positive values to negative integers.
-                np.clip(xa, -1, self.N, out=xa)
-                xa = xa.astype(int)
+            xa *= self.N
+            # Negative values are out of range, but astype(int) would
+            # truncate them towards zero.
+            xa[xa < 0] = -1
+            # xa == 1 (== N after multiplication) is not out of range.
+            xa[xa == self.N] = self.N - 1
+            # Avoid converting large positive values to negative integers.
+            np.clip(xa, -1, self.N, out=xa)
+        with np.errstate(invalid="ignore"):
+            # We need this cast for unsigned ints as well as floats
+            xa = xa.astype(int)
         # Set the over-range indices before the under-range;
         # otherwise the under-range values get converted to over-range.
         xa[xa > self.N - 1] = self._i_over

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/colors.py b/lib/matplotlib/colors.py
--- a/lib/matplotlib/colors.py
+++ b/lib/matplotlib/colors.py
@@ -712,6 +712,10 @@
         xa = np.array(X, copy=True)
         if mask_bad is None:
             mask_bad = np.isnan(xa)
+        # Ensure integer arrays have a dtype that can hold sentinel indices
+        # (e.g. self._i_under, self._i_over, self._i_bad) without overflow.
+        if xa.dtype.kind in ("u", "i"):
+            xa = xa.astype(np.int32, copy=False)
         if not xa.dtype.isnative:
             xa = xa.byteswap().newbyteorder()  # Native byteorder is faster.
         if xa.dtype.kind == "f":



######## ITEM 2-2: matplotlib__matplotlib-24970 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/lib/matplotlib/colors.py b/lib/matplotlib/colors.py
--- a/lib/matplotlib/colors.py
+++ b/lib/matplotlib/colors.py
@@ -715,16 +715,17 @@ def __call__(self, X, alpha=None, bytes=False):
         if not xa.dtype.isnative:
             xa = xa.byteswap().newbyteorder()  # Native byteorder is faster.
         if xa.dtype.kind == "f":
-            with np.errstate(invalid="ignore"):
-                xa *= self.N
-                # Negative values are out of range, but astype(int) would
-                # truncate them towards zero.
-                xa[xa < 0] = -1
-                # xa == 1 (== N after multiplication) is not out of range.
-                xa[xa == self.N] = self.N - 1
-                # Avoid converting large positive values to negative integers.
-                np.clip(xa, -1, self.N, out=xa)
-                xa = xa.astype(int)
+            xa *= self.N
+            # Negative values are out of range, but astype(int) would
+            # truncate them towards zero.
+            xa[xa < 0] = -1
+            # xa == 1 (== N after multiplication) is not out of range.
+            xa[xa == self.N] = self.N - 1
+            # Avoid converting large positive values to negative integers.
+            np.clip(xa, -1, self.N, out=xa)
+        with np.errstate(invalid="ignore"):
+            # We need this cast for unsigned ints as well as floats
+            xa = xa.astype(int)
         # Set the over-range indices before the under-range;
         # otherwise the under-range values get converted to over-range.
         xa[xa > self.N - 1] = self._i_over

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/colors.py b/lib/matplotlib/colors.py
--- a/lib/matplotlib/colors.py
+++ b/lib/matplotlib/colors.py
@@ -725,6 +725,9 @@
                 # Avoid converting large positive values to negative integers.
                 np.clip(xa, -1, self.N, out=xa)
                 xa = xa.astype(int)
+        # Ensure integer array can hold sentinel values without overflow.
+        if np.issubdtype(xa.dtype, np.integer):
+            xa = xa.astype(np.int32, copy=False)
         # Set the over-range indices before the under-range;
         # otherwise the under-range values get converted to over-range.
         xa[xa > self.N - 1] = self._i_over



######## ITEM 2-3: matplotlib__matplotlib-24970 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/lib/matplotlib/colors.py b/lib/matplotlib/colors.py
--- a/lib/matplotlib/colors.py
+++ b/lib/matplotlib/colors.py
@@ -715,16 +715,17 @@ def __call__(self, X, alpha=None, bytes=False):
         if not xa.dtype.isnative:
             xa = xa.byteswap().newbyteorder()  # Native byteorder is faster.
         if xa.dtype.kind == "f":
-            with np.errstate(invalid="ignore"):
-                xa *= self.N
-                # Negative values are out of range, but astype(int) would
-                # truncate them towards zero.
-                xa[xa < 0] = -1
-                # xa == 1 (== N after multiplication) is not out of range.
-                xa[xa == self.N] = self.N - 1
-                # Avoid converting large positive values to negative integers.
-                np.clip(xa, -1, self.N, out=xa)
-                xa = xa.astype(int)
+            xa *= self.N
+            # Negative values are out of range, but astype(int) would
+            # truncate them towards zero.
+            xa[xa < 0] = -1
+            # xa == 1 (== N after multiplication) is not out of range.
+            xa[xa == self.N] = self.N - 1
+            # Avoid converting large positive values to negative integers.
+            np.clip(xa, -1, self.N, out=xa)
+        with np.errstate(invalid="ignore"):
+            # We need this cast for unsigned ints as well as floats
+            xa = xa.astype(int)
         # Set the over-range indices before the under-range;
         # otherwise the under-range values get converted to over-range.
         xa[xa > self.N - 1] = self._i_over

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/colors.py b/lib/matplotlib/colors.py
--- a/lib/matplotlib/colors.py
+++ b/lib/matplotlib/colors.py
@@ -714,6 +714,9 @@
             mask_bad = np.isnan(xa)
         if not xa.dtype.isnative:
             xa = xa.byteswap().newbyteorder()  # Native byteorder is faster.
+        # Ensure integer arrays use a signed integer type to avoid overflow warnings
+        if xa.dtype.kind in ("i", "u"):
+            xa = xa.astype(np.int32, copy=False)
         if xa.dtype.kind == "f":
             with np.errstate(invalid="ignore"):
                 xa *= self.N



######## ITEM 2-4: matplotlib__matplotlib-24970 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/lib/matplotlib/colors.py b/lib/matplotlib/colors.py
--- a/lib/matplotlib/colors.py
+++ b/lib/matplotlib/colors.py
@@ -715,16 +715,17 @@ def __call__(self, X, alpha=None, bytes=False):
         if not xa.dtype.isnative:
             xa = xa.byteswap().newbyteorder()  # Native byteorder is faster.
         if xa.dtype.kind == "f":
-            with np.errstate(invalid="ignore"):
-                xa *= self.N
-                # Negative values are out of range, but astype(int) would
-                # truncate them towards zero.
-                xa[xa < 0] = -1
-                # xa == 1 (== N after multiplication) is not out of range.
-                xa[xa == self.N] = self.N - 1
-                # Avoid converting large positive values to negative integers.
-                np.clip(xa, -1, self.N, out=xa)
-                xa = xa.astype(int)
+            xa *= self.N
+            # Negative values are out of range, but astype(int) would
+            # truncate them towards zero.
+            xa[xa < 0] = -1
+            # xa == 1 (== N after multiplication) is not out of range.
+            xa[xa == self.N] = self.N - 1
+            # Avoid converting large positive values to negative integers.
+            np.clip(xa, -1, self.N, out=xa)
+        with np.errstate(invalid="ignore"):
+            # We need this cast for unsigned ints as well as floats
+            xa = xa.astype(int)
         # Set the over-range indices before the under-range;
         # otherwise the under-range values get converted to over-range.
         xa[xa > self.N - 1] = self._i_over

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/colors.py b/lib/matplotlib/colors.py
--- a/lib/matplotlib/colors.py
+++ b/lib/matplotlib/colors.py
@@ -727,6 +727,9 @@
                 xa = xa.astype(int)
         # Set the over-range indices before the under-range;
         # otherwise the under-range values get converted to over-range.
+        if xa.dtype.kind in ("i", "u"):
+            # Convert to a signed integer type that can hold values up to self._i_over
+            xa = xa.astype(np.int64)
         xa[xa > self.N - 1] = self._i_over
         xa[xa < 0] = self._i_under
         xa[mask_bad] = self._i_bad



######## ITEM 2-5: matplotlib__matplotlib-24970 (gpt-oss-20b s2)
=== GOLD PATCH
diff --git a/lib/matplotlib/colors.py b/lib/matplotlib/colors.py
--- a/lib/matplotlib/colors.py
+++ b/lib/matplotlib/colors.py
@@ -715,16 +715,17 @@ def __call__(self, X, alpha=None, bytes=False):
         if not xa.dtype.isnative:
             xa = xa.byteswap().newbyteorder()  # Native byteorder is faster.
         if xa.dtype.kind == "f":
-            with np.errstate(invalid="ignore"):
-                xa *= self.N
-                # Negative values are out of range, but astype(int) would
-                # truncate them towards zero.
-                xa[xa < 0] = -1
-                # xa == 1 (== N after multiplication) is not out of range.
-                xa[xa == self.N] = self.N - 1
-                # Avoid converting large positive values to negative integers.
-                np.clip(xa, -1, self.N, out=xa)
-                xa = xa.astype(int)
+            xa *= self.N
+            # Negative values are out of range, but astype(int) would
+            # truncate them towards zero.
+            xa[xa < 0] = -1
+            # xa == 1 (== N after multiplication) is not out of range.
+            xa[xa == self.N] = self.N - 1
+            # Avoid converting large positive values to negative integers.
+            np.clip(xa, -1, self.N, out=xa)
+        with np.errstate(invalid="ignore"):
+            # We need this cast for unsigned ints as well as floats
+            xa = xa.astype(int)
         # Set the over-range indices before the under-range;
         # otherwise the under-range values get converted to over-range.
         xa[xa > self.N - 1] = self._i_over

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/colors.py b/lib/matplotlib/colors.py
--- a/lib/matplotlib/colors.py
+++ b/lib/matplotlib/colors.py
@@ -710,6 +710,10 @@
         # np.isnan() to after we have converted to an array.
         mask_bad = X.mask if np.ma.is_masked(X) else None
         xa = np.array(X, copy=True)
+        # Avoid NumPy 1.24 deprecation warning for integer types by
+        # ensuring xa is an integer array before indexing.
+        if xa.dtype.kind != "f":
+            xa = xa.astype(int, copy=False)
         if mask_bad is None:
             mask_bad = np.isnan(xa)
         if not xa.dtype.isnative:



######## ITEM 2-6: matplotlib__matplotlib-25311 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1505,7 +1505,6 @@ def __init__(self, ref_artist, use_blit=False):
         if not ref_artist.pickable():
             ref_artist.set_picker(True)
         self.got_artist = False
-        self.canvas = self.ref_artist.figure.canvas
         self._use_blit = use_blit and self.canvas.supports_blit
         self.cids = [
             self.canvas.callbacks._connect_picklable(
@@ -1514,6 +1513,9 @@ def __init__(self, ref_artist, use_blit=False):
                 'button_release_event', self.on_release),
         ]
 
+    # A property, not an attribute, to maintain picklability.
+    canvas = property(lambda self: self.ref_artist.figure.canvas)
+
     def on_motion(self, evt):
         if self._check_still_parented() and self.got_artist:
             dx = evt.x - self.mouse_x

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1514,6 +1514,31 @@
                 'button_release_event', self.on_release),
         ]
 
+    # ----------------------------------------------------------------------
+    # Pickling support
+    # ----------------------------------------------------------------------
+    def __getstate__(self):
+        """
+        Return state for pickling, omitting unpicklable attributes such as the
+        canvas and callback identifiers.
+        """
+        state = self.__dict__.copy()
+        # ``canvas`` holds a reference to a GUI backend which cannot be pickled.
+        state.pop('canvas', None)
+        # Callback identifiers are integers tied to the live canvas; they are
+        # not needed (and not valid) after unpickling.
+        state.pop('cids', None)
+        state.pop('_c1', None)
+        return state
+
+    def __setstate__(self, state):
+        """
+        Restore state after unpickling.  The ``canvas`` attribute will be set
+        later when the draggable object is re‑attached to a figure (e.g. via
+        ``set_figure``).  Missing attributes are simply ignored.
+        """
+        self.__dict__.update(state)
+
     def on_motion(self, evt):
         if self._check_still_parented() and self.got_artist:
             dx = evt.x - self.mouse_x



######## ITEM 2-7: matplotlib__matplotlib-25311 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1505,7 +1505,6 @@ def __init__(self, ref_artist, use_blit=False):
         if not ref_artist.pickable():
             ref_artist.set_picker(True)
         self.got_artist = False
-        self.canvas = self.ref_artist.figure.canvas
         self._use_blit = use_blit and self.canvas.supports_blit
         self.cids = [
             self.canvas.callbacks._connect_picklable(
@@ -1514,6 +1513,9 @@ def __init__(self, ref_artist, use_blit=False):
                 'button_release_event', self.on_release),
         ]
 
+    # A property, not an attribute, to maintain picklability.
+    canvas = property(lambda self: self.ref_artist.figure.canvas)
+
     def on_motion(self, evt):
         if self._check_still_parented() and self.got_artist:
             dx = evt.x - self.mouse_x

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1514,6 +1514,17 @@
                 'button_release_event', self.on_release),
         ]
 
+    def __getstate__(self):
+        """
+        Return state for pickling, excluding unpicklable canvas‐related
+        attributes.
+        """
+        state = self.__dict__.copy()
+        # These attributes reference the GUI backend which cannot be pickled.
+        for attr in ('canvas', 'cids', '_c1'):
+            state.pop(attr, None)
+        return state
+
     def on_motion(self, evt):
         if self._check_still_parented() and self.got_artist:
             dx = evt.x - self.mouse_x



######## ITEM 2-8: matplotlib__matplotlib-25311 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1505,7 +1505,6 @@ def __init__(self, ref_artist, use_blit=False):
         if not ref_artist.pickable():
             ref_artist.set_picker(True)
         self.got_artist = False
-        self.canvas = self.ref_artist.figure.canvas
         self._use_blit = use_blit and self.canvas.supports_blit
         self.cids = [
             self.canvas.callbacks._connect_picklable(
@@ -1514,6 +1513,9 @@ def __init__(self, ref_artist, use_blit=False):
                 'button_release_event', self.on_release),
         ]
 
+    # A property, not an attribute, to maintain picklability.
+    canvas = property(lambda self: self.ref_artist.figure.canvas)
+
     def on_motion(self, evt):
         if self._check_still_parented() and self.got_artist:
             dx = evt.x - self.mouse_x

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1514,6 +1514,26 @@
                 'button_release_event', self.on_release),
         ]
 
+    def __getstate__(self):
+        """
+        Return state without unpickleable canvas and callback ids.
+        """
+        state = self.__dict__.copy()
+        # Remove attributes that cannot be pickled.
+        state.pop('canvas', None)
+        state.pop('cids', None)
+        state.pop('_c1', None)
+        return state
+
+    def __setstate__(self, state):
+        """
+        Restore state. Canvas and callbacks will be reinitialized lazily.
+        """
+        self.__dict__.update(state)
+        # Ensure attributes that were removed are reset to safe defaults.
+        self.canvas = None
+        self.cids = []
+
     def on_motion(self, evt):
         if self._check_still_parented() and self.got_artist:
             dx = evt.x - self.mouse_x



######## ITEM 2-9: matplotlib__matplotlib-25311 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1505,7 +1505,6 @@ def __init__(self, ref_artist, use_blit=False):
         if not ref_artist.pickable():
             ref_artist.set_picker(True)
         self.got_artist = False
-        self.canvas = self.ref_artist.figure.canvas
         self._use_blit = use_blit and self.canvas.supports_blit
         self.cids = [
             self.canvas.callbacks._connect_picklable(
@@ -1514,6 +1513,9 @@ def __init__(self, ref_artist, use_blit=False):
                 'button_release_event', self.on_release),
         ]
 
+    # A property, not an attribute, to maintain picklability.
+    canvas = property(lambda self: self.ref_artist.figure.canvas)
+
     def on_motion(self, evt):
         if self._check_still_parented() and self.got_artist:
             dx = evt.x - self.mouse_x

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1514,6 +1514,12 @@
                 'button_release_event', self.on_release),
         ]
 
+    def __getstate__(self):
+        # Exclude the canvas reference which is not picklable
+        state = self.__dict__.copy()
+        state.pop('canvas', None)
+        return state
+
     def on_motion(self, evt):
         if self._check_still_parented() and self.got_artist:
             dx = evt.x - self.mouse_x



######## ITEM 2-10: matplotlib__matplotlib-25311 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1505,7 +1505,6 @@ def __init__(self, ref_artist, use_blit=False):
         if not ref_artist.pickable():
             ref_artist.set_picker(True)
         self.got_artist = False
-        self.canvas = self.ref_artist.figure.canvas
         self._use_blit = use_blit and self.canvas.supports_blit
         self.cids = [
             self.canvas.callbacks._connect_picklable(
@@ -1514,6 +1513,9 @@ def __init__(self, ref_artist, use_blit=False):
                 'button_release_event', self.on_release),
         ]
 
+    # A property, not an attribute, to maintain picklability.
+    canvas = property(lambda self: self.ref_artist.figure.canvas)
+
     def on_motion(self, evt):
         if self._check_still_parented() and self.got_artist:
             dx = evt.x - self.mouse_x

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/offsetbox.py b/lib/matplotlib/offsetbox.py
--- a/lib/matplotlib/offsetbox.py
+++ b/lib/matplotlib/offsetbox.py
@@ -1514,6 +1514,14 @@
                 'button_release_event', self.on_release),
         ]
 
+    def __getstate__(self):
+        """Return a pickleable state, excluding non-pickleable attributes."""
+        state = self.__dict__.copy()
+        # The canvas and callback ids cannot be pickled; drop them.
+        for key in ('canvas', 'cids', '_c1'):
+            state.pop(key, None)
+        return state
+
     def on_motion(self, evt):
         if self._check_still_parented() and self.got_artist:
             dx = evt.x - self.mouse_x



######## ITEM 2-11: pydata__xarray-3151 (gemma26 s0)
=== GOLD PATCH
diff --git a/xarray/core/combine.py b/xarray/core/combine.py
--- a/xarray/core/combine.py
+++ b/xarray/core/combine.py
@@ -501,14 +501,13 @@ def combine_by_coords(datasets, compat='no_conflicts', data_vars='all',
                                    fill_value=fill_value)
 
         # Check the overall coordinates are monotonically increasing
-        for dim in concatenated.dims:
-            if dim in concatenated:
-                indexes = concatenated.indexes.get(dim)
-                if not (indexes.is_monotonic_increasing
-                        or indexes.is_monotonic_decreasing):
-                    raise ValueError("Resulting object does not have monotonic"
-                                     " global indexes along dimension {}"
-                                     .format(dim))
+        for dim in concat_dims:
+            indexes = concatenated.indexes.get(dim)
+            if not (indexes.is_monotonic_increasing
+                    or indexes.is_monotonic_decreasing):
+                raise ValueError("Resulting object does not have monotonic"
+                                 " global indexes along dimension {}"
+                                 .format(dim))
         concatenated_grouped_by_data_vars.append(concatenated)
 
     return merge(concatenated_grouped_by_data_vars, compat=compat,

=== CANDIDATE PATCH
diff --git a/xarray/core/combine.py b/xarray/core/combine.py
--- a/xarray/core/combine.py
+++ b/xarray/core/combine.py
@@ -501,7 +501,7 @@
                                    fill_value=fill_value)
 
         # Check the overall coordinates are monotonically increasing
-        for dim in concatenated.dims:
+        for dim in concat_dims:
             if dim in concatenated:
                 indexes = concatenated.indexes.get(dim)
                 if not (indexes.is_monotonic_increasing



######## ITEM 2-12: pydata__xarray-3151 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/xarray/core/combine.py b/xarray/core/combine.py
--- a/xarray/core/combine.py
+++ b/xarray/core/combine.py
@@ -501,14 +501,13 @@ def combine_by_coords(datasets, compat='no_conflicts', data_vars='all',
                                    fill_value=fill_value)
 
         # Check the overall coordinates are monotonically increasing
-        for dim in concatenated.dims:
-            if dim in concatenated:
-                indexes = concatenated.indexes.get(dim)
-                if not (indexes.is_monotonic_increasing
-                        or indexes.is_monotonic_decreasing):
-                    raise ValueError("Resulting object does not have monotonic"
-                                     " global indexes along dimension {}"
-                                     .format(dim))
+        for dim in concat_dims:
+            indexes = concatenated.indexes.get(dim)
+            if not (indexes.is_monotonic_increasing
+                    or indexes.is_monotonic_decreasing):
+                raise ValueError("Resulting object does not have monotonic"
+                                 " global indexes along dimension {}"
+                                 .format(dim))
         concatenated_grouped_by_data_vars.append(concatenated)
 
     return merge(concatenated_grouped_by_data_vars, compat=compat,

=== CANDIDATE PATCH
diff --git a/xarray/core/combine.py b/xarray/core/combine.py
--- a/xarray/core/combine.py
+++ b/xarray/core/combine.py
@@ -500,8 +500,10 @@
                                    data_vars=data_vars, coords=coords,
                                    fill_value=fill_value)
 
-        # Check the overall coordinates are monotonically increasing
-        for dim in concatenated.dims:
+        # Check that concatenated dimensions have monotonic coordinates.
+        # Dimensions that were identical across all input datasets are not
+        # required to be monotonic.
+        for dim in concat_dims:
             if dim in concatenated:
                 indexes = concatenated.indexes.get(dim)
                 if not (indexes.is_monotonic_increasing



######## ITEM 2-13: pydata__xarray-3151 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/xarray/core/combine.py b/xarray/core/combine.py
--- a/xarray/core/combine.py
+++ b/xarray/core/combine.py
@@ -501,14 +501,13 @@ def combine_by_coords(datasets, compat='no_conflicts', data_vars='all',
                                    fill_value=fill_value)
 
         # Check the overall coordinates are monotonically increasing
-        for dim in concatenated.dims:
-            if dim in concatenated:
-                indexes = concatenated.indexes.get(dim)
-                if not (indexes.is_monotonic_increasing
-                        or indexes.is_monotonic_decreasing):
-                    raise ValueError("Resulting object does not have monotonic"
-                                     " global indexes along dimension {}"
-                                     .format(dim))
+        for dim in concat_dims:
+            indexes = concatenated.indexes.get(dim)
+            if not (indexes.is_monotonic_increasing
+                    or indexes.is_monotonic_decreasing):
+                raise ValueError("Resulting object does not have monotonic"
+                                 " global indexes along dimension {}"
+                                 .format(dim))
         concatenated_grouped_by_data_vars.append(concatenated)
 
     return merge(concatenated_grouped_by_data_vars, compat=compat,

=== CANDIDATE PATCH
diff --git a/xarray/core/combine.py b/xarray/core/combine.py
--- a/xarray/core/combine.py
+++ b/xarray/core/combine.py
@@ -501,14 +501,13 @@
                                    fill_value=fill_value)
 
         # Check the overall coordinates are monotonically increasing
-        for dim in concatenated.dims:
-            if dim in concatenated:
-                indexes = concatenated.indexes.get(dim)
-                if not (indexes.is_monotonic_increasing
-                        or indexes.is_monotonic_decreasing):
-                    raise ValueError("Resulting object does not have monotonic"
-                                     " global indexes along dimension {}"
-                                     .format(dim))
+        for dim in concat_dims:
+            indexes = concatenated.indexes.get(dim)
+            if indexes is not None and not (indexes.is_monotonic_increasing
+                                            or indexes.is_monotonic_decreasing):
+                raise ValueError("Resulting object does not have monotonic"
+                                 " global indexes along dimension {}"
+                                 .format(dim))
         concatenated_grouped_by_data_vars.append(concatenated)
 
     return merge(concatenated_grouped_by_data_vars, compat=compat,



######## ITEM 2-14: pydata__xarray-3151 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/xarray/core/combine.py b/xarray/core/combine.py
--- a/xarray/core/combine.py
+++ b/xarray/core/combine.py
@@ -501,14 +501,13 @@ def combine_by_coords(datasets, compat='no_conflicts', data_vars='all',
                                    fill_value=fill_value)
 
         # Check the overall coordinates are monotonically increasing
-        for dim in concatenated.dims:
-            if dim in concatenated:
-                indexes = concatenated.indexes.get(dim)
-                if not (indexes.is_monotonic_increasing
-                        or indexes.is_monotonic_decreasing):
-                    raise ValueError("Resulting object does not have monotonic"
-                                     " global indexes along dimension {}"
-                                     .format(dim))
+        for dim in concat_dims:
+            indexes = concatenated.indexes.get(dim)
+            if not (indexes.is_monotonic_increasing
+                    or indexes.is_monotonic_decreasing):
+                raise ValueError("Resulting object does not have monotonic"
+                                 " global indexes along dimension {}"
+                                 .format(dim))
         concatenated_grouped_by_data_vars.append(concatenated)
 
     return merge(concatenated_grouped_by_data_vars, compat=compat,

=== CANDIDATE PATCH
diff --git a/xarray/core/combine.py b/xarray/core/combine.py
--- a/xarray/core/combine.py
+++ b/xarray/core/combine.py
@@ -500,15 +500,17 @@
                                    data_vars=data_vars, coords=coords,
                                    fill_value=fill_value)
 
-        # Check the overall coordinates are monotonically increasing
-        for dim in concatenated.dims:
-            if dim in concatenated:
-                indexes = concatenated.indexes.get(dim)
-                if not (indexes.is_monotonic_increasing
-                        or indexes.is_monotonic_decreasing):
-                    raise ValueError("Resulting object does not have monotonic"
-                                     " global indexes along dimension {}"
-                                     .format(dim))
+        # Check that the concatenated dimensions have monotonic coordinates.
+        # Dimensions that did not vary across the input datasets are ignored,
+        # as they are treated as "bystander" coordinates.
+        for dim in concat_dims:
+            indexes = concatenated.indexes.get(dim)
+            if not (indexes.is_monotonic_increasing
+                    or indexes.is_monotonic_decreasing):
+                raise ValueError(
+                    "Resulting object does not have monotonic global indexes "
+                    "along dimension {}".format(dim)
+                )
         concatenated_grouped_by_data_vars.append(concatenated)
 
     return merge(concatenated_grouped_by_data_vars, compat=compat,



######## ITEM 2-15: pydata__xarray-3151 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/xarray/core/combine.py b/xarray/core/combine.py
--- a/xarray/core/combine.py
+++ b/xarray/core/combine.py
@@ -501,14 +501,13 @@ def combine_by_coords(datasets, compat='no_conflicts', data_vars='all',
                                    fill_value=fill_value)
 
         # Check the overall coordinates are monotonically increasing
-        for dim in concatenated.dims:
-            if dim in concatenated:
-                indexes = concatenated.indexes.get(dim)
-                if not (indexes.is_monotonic_increasing
-                        or indexes.is_monotonic_decreasing):
-                    raise ValueError("Resulting object does not have monotonic"
-                                     " global indexes along dimension {}"
-                                     .format(dim))
+        for dim in concat_dims:
+            indexes = concatenated.indexes.get(dim)
+            if not (indexes.is_monotonic_increasing
+                    or indexes.is_monotonic_decreasing):
+                raise ValueError("Resulting object does not have monotonic"
+                                 " global indexes along dimension {}"
+                                 .format(dim))
         concatenated_grouped_by_data_vars.append(concatenated)
 
     return merge(concatenated_grouped_by_data_vars, compat=compat,

=== CANDIDATE PATCH
diff --git a/xarray/core/combine.py b/xarray/core/combine.py
--- a/xarray/core/combine.py
+++ b/xarray/core/combine.py
@@ -502,7 +502,7 @@
 
         # Check the overall coordinates are monotonically increasing
         for dim in concatenated.dims:
-            if dim in concatenated:
+            if dim in concatenated and dim in concat_dims:
                 indexes = concatenated.indexes.get(dim)
                 if not (indexes.is_monotonic_increasing
                         or indexes.is_monotonic_decreasing):



######## ITEM 2-16: pydata__xarray-3151 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/xarray/core/combine.py b/xarray/core/combine.py
--- a/xarray/core/combine.py
+++ b/xarray/core/combine.py
@@ -501,14 +501,13 @@ def combine_by_coords(datasets, compat='no_conflicts', data_vars='all',
                                    fill_value=fill_value)
 
         # Check the overall coordinates are monotonically increasing
-        for dim in concatenated.dims:
-            if dim in concatenated:
-                indexes = concatenated.indexes.get(dim)
-                if not (indexes.is_monotonic_increasing
-                        or indexes.is_monotonic_decreasing):
-                    raise ValueError("Resulting object does not have monotonic"
-                                     " global indexes along dimension {}"
-                                     .format(dim))
+        for dim in concat_dims:
+            indexes = concatenated.indexes.get(dim)
+            if not (indexes.is_monotonic_increasing
+                    or indexes.is_monotonic_decreasing):
+                raise ValueError("Resulting object does not have monotonic"
+                                 " global indexes along dimension {}"
+                                 .format(dim))
         concatenated_grouped_by_data_vars.append(concatenated)
 
     return merge(concatenated_grouped_by_data_vars, compat=compat,

=== CANDIDATE PATCH
diff --git a/xarray/core/combine.py b/xarray/core/combine.py
--- a/xarray/core/combine.py
+++ b/xarray/core/combine.py
@@ -502,7 +502,7 @@
 
         # Check the overall coordinates are monotonically increasing
         for dim in concatenated.dims:
-            if dim in concatenated:
+            if dim in concat_dims:
                 indexes = concatenated.indexes.get(dim)
                 if not (indexes.is_monotonic_increasing
                         or indexes.is_monotonic_decreasing):



######## ITEM 2-17: pydata__xarray-4094 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/xarray/core/dataarray.py b/xarray/core/dataarray.py
--- a/xarray/core/dataarray.py
+++ b/xarray/core/dataarray.py
@@ -1961,7 +1961,7 @@ def to_unstacked_dataset(self, dim, level=0):
         # pull variables out of datarray
         data_dict = {}
         for k in variables:
-            data_dict[k] = self.sel({variable_dim: k}).squeeze(drop=True)
+            data_dict[k] = self.sel({variable_dim: k}, drop=True).squeeze(drop=True)
 
         # unstacked dataset
         return Dataset(data_dict)

=== CANDIDATE PATCH
diff --git a/xarray/core/dataarray.py b/xarray/core/dataarray.py
--- a/xarray/core/dataarray.py
+++ b/xarray/core/dataarray.py
@@ -1961,7 +1961,11 @@
         # pull variables out of datarray
         data_dict = {}
         for k in variables:
-            data_dict[k] = self.sel({variable_dim: k}).squeeze(drop=True)
+            da = self.sel({variable_dim: k}).squeeze(drop=True)
+            # drop the stacked coordinate (``dim``) to avoid merge conflicts
+            if dim in da.coords:
+                da = da.drop_vars(dim)
+            data_dict[k] = da
 
         # unstacked dataset
         return Dataset(data_dict)



######## ITEM 2-18: pydata__xarray-4094 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/xarray/core/dataarray.py b/xarray/core/dataarray.py
--- a/xarray/core/dataarray.py
+++ b/xarray/core/dataarray.py
@@ -1961,7 +1961,7 @@ def to_unstacked_dataset(self, dim, level=0):
         # pull variables out of datarray
         data_dict = {}
         for k in variables:
-            data_dict[k] = self.sel({variable_dim: k}).squeeze(drop=True)
+            data_dict[k] = self.sel({variable_dim: k}, drop=True).squeeze(drop=True)
 
         # unstacked dataset
         return Dataset(data_dict)

=== CANDIDATE PATCH
diff --git a/xarray/core/dataarray.py b/xarray/core/dataarray.py
--- a/xarray/core/dataarray.py
+++ b/xarray/core/dataarray.py
@@ -1961,7 +1961,13 @@
         # pull variables out of datarray
         data_dict = {}
         for k in variables:
-            data_dict[k] = self.sel({variable_dim: k}).squeeze(drop=True)
+            # Select the slice for each variable and drop the stacked coordinate
+            # to avoid duplicate coordinate variables when constructing the Dataset.
+            data_dict[k] = (
+                self.sel({variable_dim: k})
+                .squeeze(drop=True)
+                .drop_vars(dim, errors="ignore")
+            )
 
         # unstacked dataset
         return Dataset(data_dict)



######## ITEM 2-19: pydata__xarray-4356 (gemma26 s0)
=== GOLD PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,13 +26,9 @@ def _maybe_null_out(result, axis, mask, min_count=1):
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
 
     if axis is not None and getattr(result, "ndim", False):
-        null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+        null_mask = (np.take(mask.shape, axis).prod() - mask.sum(axis) - min_count) < 0
         if null_mask.any():
             dtype, fill_value = dtypes.maybe_promote(result.dtype)
             result = result.astype(dtype)

=== CANDIDATE PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,13 +26,14 @@
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
-
     if axis is not None and getattr(result, "ndim", False):
-        null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+        if hasattr(axis, "__len__"):  # if tuple or list
+            # Calculate the product of shapes of the axes being reduced
+            shape = np.prod([mask.shape[i] for i in axis])
+            null_mask = (shape - mask.sum(axis) - min_count) < 0
+        else:
+            null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+
         if null_mask.any():
             dtype, fill_value = dtypes.maybe_promote(result.dtype)
             result = result.astype(dtype)



######## ITEM 2-20: pydata__xarray-4356 (gemma26 s1)
=== GOLD PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,13 +26,9 @@ def _maybe_null_out(result, axis, mask, min_count=1):
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
 
     if axis is not None and getattr(result, "ndim", False):
-        null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+        null_mask = (np.take(mask.shape, axis).prod() - mask.sum(axis) - min_count) < 0
         if null_mask.any():
             dtype, fill_value = dtypes.maybe_promote(result.dtype)
             result = result.astype(dtype)

=== CANDIDATE PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,13 +26,13 @@
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
-
     if axis is not None and getattr(result, "ndim", False):
-        null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+        if isinstance(axis, (list, tuple)):
+            shape = np.prod([mask.shape[i] for i in axis])
+        else:
+            shape = mask.shape[axis]
+
+        null_mask = (shape - mask.sum(axis) - min_count) < 0
         if null_mask.any():
             dtype, fill_value = dtypes.maybe_promote(result.dtype)
             result = result.astype(dtype)



######## ITEM 2-21: pydata__xarray-4356 (gemma26 s2)
=== GOLD PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,13 +26,9 @@ def _maybe_null_out(result, axis, mask, min_count=1):
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
 
     if axis is not None and getattr(result, "ndim", False):
-        null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+        null_mask = (np.take(mask.shape, axis).prod() - mask.sum(axis) - min_count) < 0
         if null_mask.any():
             dtype, fill_value = dtypes.maybe_promote(result.dtype)
             result = result.astype(dtype)

=== CANDIDATE PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,13 +26,13 @@
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
-
     if axis is not None and getattr(result, "ndim", False):
-        null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+        if isinstance(axis, (list, tuple)):
+            reduction_size = np.prod([mask.shape[i] for i in axis])
+        else:
+            reduction_size = mask.shape[axis]
+
+        null_mask = (reduction_size - mask.sum(axis) - min_count) < 0
         if null_mask.any():
             dtype, fill_value = dtypes.maybe_promote(result.dtype)
             result = result.astype(dtype)



######## ITEM 2-22: pydata__xarray-4356 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,13 +26,9 @@ def _maybe_null_out(result, axis, mask, min_count=1):
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
 
     if axis is not None and getattr(result, "ndim", False):
-        null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+        null_mask = (np.take(mask.shape, axis).prod() - mask.sum(axis) - min_count) < 0
         if null_mask.any():
             dtype, fill_value = dtypes.maybe_promote(result.dtype)
             result = result.astype(dtype)

=== CANDIDATE PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,13 +26,15 @@
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
+    # Allow `axis` to be a tuple/list for reductions over multiple dimensions.
 
     if axis is not None and getattr(result, "ndim", False):
-        null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+        # total number of elements reduced over (supports tuple/list of axes)
+        if hasattr(axis, "__len__"):
+            total = np.take(mask.shape, axis).prod()
+        else:
+            total = mask.shape[axis]
+        null_mask = (total - mask.sum(axis) - min_count) < 0
         if null_mask.any():
             dtype, fill_value = dtypes.maybe_promote(result.dtype)
             result = result.astype(dtype)



######## ITEM 2-23: pydata__xarray-4356 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,13 +26,9 @@ def _maybe_null_out(result, axis, mask, min_count=1):
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
 
     if axis is not None and getattr(result, "ndim", False):
-        null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+        null_mask = (np.take(mask.shape, axis).prod() - mask.sum(axis) - min_count) < 0
         if null_mask.any():
             dtype, fill_value = dtypes.maybe_promote(result.dtype)
             result = result.astype(dtype)

=== CANDIDATE PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -27,9 +27,14 @@
     xarray version of pandas.core.nanops._maybe_null_out
     """
     if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
+        # compute total number of elements reduced over the specified axes
+        total = np.take(mask.shape, axis).prod()
+        null_mask = (total - mask.sum(axis=axis) - min_count) < 0
+        if null_mask.any():
+            dtype, fill_value = dtypes.maybe_promote(result.dtype)
+            result = result.astype(dtype)
+            result[null_mask] = fill_value
+        return result
 
     if axis is not None and getattr(result, "ndim", False):
         null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0



######## ITEM 2-24: pydata__xarray-4356 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,13 +26,9 @@ def _maybe_null_out(result, axis, mask, min_count=1):
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
 
     if axis is not None and getattr(result, "ndim", False):
-        null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+        null_mask = (np.take(mask.shape, axis).prod() - mask.sum(axis) - min_count) < 0
         if null_mask.any():
             dtype, fill_value = dtypes.maybe_promote(result.dtype)
             result = result.astype(dtype)

=== CANDIDATE PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -27,9 +27,13 @@
     xarray version of pandas.core.nanops._maybe_null_out
     """
     if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
+        # compute number of valid elements along the specified axes
+        shape_prod = np.take(mask.shape, axis).prod()
+        null_mask = (shape_prod - mask.sum(axis) - min_count) < 0
+        if null_mask.any():
+            dtype, fill_value = dtypes.maybe_promote(result.dtype)
+            result = result.astype(dtype)
+            result[null_mask] = fill_value
 
     if axis is not None and getattr(result, "ndim", False):
         null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0



######## ITEM 2-25: pydata__xarray-4356 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,13 +26,9 @@ def _maybe_null_out(result, axis, mask, min_count=1):
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
 
     if axis is not None and getattr(result, "ndim", False):
-        null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+        null_mask = (np.take(mask.shape, axis).prod() - mask.sum(axis) - min_count) < 0
         if null_mask.any():
             dtype, fill_value = dtypes.maybe_promote(result.dtype)
             result = result.astype(dtype)

=== CANDIDATE PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,10 +26,17 @@
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
+    # Support `min_count` for reductions over multiple axes
+    if isinstance(axis, (list, tuple)):
+        # Compute the total number of elements along the reduced axes
+        reduced_shape = tuple(mask.shape[ax] for ax in axis)
+        total = np.prod(reduced_shape)
+        null_mask = (total - mask.sum(axis=axis) - min_count) < 0
+        if null_mask.any():
+            dtype, fill_value = dtypes.maybe_promote(result.dtype)
+            result = result.astype(dtype)
+            result[null_mask] = fill_value
+        return result
 
     if axis is not None and getattr(result, "ndim", False):
         null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0



######## ITEM 2-26: pydata__xarray-4356 (gpt-oss-20b s2)
=== GOLD PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -26,13 +26,9 @@ def _maybe_null_out(result, axis, mask, min_count=1):
     """
     xarray version of pandas.core.nanops._maybe_null_out
     """
-    if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
 
     if axis is not None and getattr(result, "ndim", False):
-        null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0
+        null_mask = (np.take(mask.shape, axis).prod() - mask.sum(axis) - min_count) < 0
         if null_mask.any():
             dtype, fill_value = dtypes.maybe_promote(result.dtype)
             result = result.astype(dtype)

=== CANDIDATE PATCH
diff --git a/xarray/core/nanops.py b/xarray/core/nanops.py
--- a/xarray/core/nanops.py
+++ b/xarray/core/nanops.py
@@ -27,9 +27,11 @@
     xarray version of pandas.core.nanops._maybe_null_out
     """
     if hasattr(axis, "__len__"):  # if tuple or list
-        raise ValueError(
-            "min_count is not available for reduction with more than one dimensions."
-        )
+        null_mask = (np.take(mask.shape, axis).prod() - mask.sum(axis) - min_count) < 0
+        if null_mask.any():
+            dtype, fill_value = dtypes.maybe_promote(result.dtype)
+            result = result.astype(dtype)
+            result[null_mask] = fill_value
 
     if axis is not None and getattr(result, "ndim", False):
         null_mask = (mask.shape[axis] - mask.sum(axis) - min_count) < 0



######## ITEM 2-27: pydata__xarray-4966 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/xarray/coding/variables.py b/xarray/coding/variables.py
--- a/xarray/coding/variables.py
+++ b/xarray/coding/variables.py
@@ -316,6 +316,14 @@ def decode(self, variable, name=None):
                     if "_FillValue" in attrs:
                         new_fill = unsigned_dtype.type(attrs["_FillValue"])
                         attrs["_FillValue"] = new_fill
+            elif data.dtype.kind == "u":
+                if unsigned == "false":
+                    signed_dtype = np.dtype("i%s" % data.dtype.itemsize)
+                    transform = partial(np.asarray, dtype=signed_dtype)
+                    data = lazy_elemwise_func(data, transform, signed_dtype)
+                    if "_FillValue" in attrs:
+                        new_fill = signed_dtype.type(attrs["_FillValue"])
+                        attrs["_FillValue"] = new_fill
             else:
                 warnings.warn(
                     "variable %r has _Unsigned attribute but is not "

=== CANDIDATE PATCH
diff --git a/xarray/coding/variables.py b/xarray/coding/variables.py
--- a/xarray/coding/variables.py
+++ b/xarray/coding/variables.py
@@ -308,6 +308,9 @@
         if "_Unsigned" in attrs:
             unsigned = pop_to(attrs, encoding, "_Unsigned")
 
+            # Handle NetCDF signed/unsigned byte conventions.
+            # ``_Unsigned="true"`` means a signed integer should be interpreted as unsigned.
+            # ``_Unsigned="false"`` (used by OPeNDAP) means an unsigned integer should be interpreted as signed.
             if data.dtype.kind == "i":
                 if unsigned == "true":
                     unsigned_dtype = np.dtype("u%s" % data.dtype.itemsize)
@@ -316,6 +319,14 @@
                     if "_FillValue" in attrs:
                         new_fill = unsigned_dtype.type(attrs["_FillValue"])
                         attrs["_FillValue"] = new_fill
+            elif data.dtype.kind == "u":
+                if unsigned == "false":
+                    signed_dtype = np.dtype("i%s" % data.dtype.itemsize)
+                    transform = partial(np.asarray, dtype=signed_dtype)
+                    data = lazy_elemwise_func(data, transform, signed_dtype)
+                    if "_FillValue" in attrs:
+                        new_fill = signed_dtype.type(attrs["_FillValue"])
+                        attrs["_FillValue"] = new_fill
             else:
                 warnings.warn(
                     "variable %r has _Unsigned attribute but is not "



######## ITEM 2-28: pydata__xarray-4966 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/xarray/coding/variables.py b/xarray/coding/variables.py
--- a/xarray/coding/variables.py
+++ b/xarray/coding/variables.py
@@ -316,6 +316,14 @@ def decode(self, variable, name=None):
                     if "_FillValue" in attrs:
                         new_fill = unsigned_dtype.type(attrs["_FillValue"])
                         attrs["_FillValue"] = new_fill
+            elif data.dtype.kind == "u":
+                if unsigned == "false":
+                    signed_dtype = np.dtype("i%s" % data.dtype.itemsize)
+                    transform = partial(np.asarray, dtype=signed_dtype)
+                    data = lazy_elemwise_func(data, transform, signed_dtype)
+                    if "_FillValue" in attrs:
+                        new_fill = signed_dtype.type(attrs["_FillValue"])
+                        attrs["_FillValue"] = new_fill
             else:
                 warnings.warn(
                     "variable %r has _Unsigned attribute but is not "

=== CANDIDATE PATCH
diff --git a/xarray/coding/variables.py b/xarray/coding/variables.py
--- a/xarray/coding/variables.py
+++ b/xarray/coding/variables.py
@@ -308,18 +308,30 @@
         if "_Unsigned" in attrs:
             unsigned = pop_to(attrs, encoding, "_Unsigned")
 
-            if data.dtype.kind == "i":
-                if unsigned == "true":
-                    unsigned_dtype = np.dtype("u%s" % data.dtype.itemsize)
-                    transform = partial(np.asarray, dtype=unsigned_dtype)
-                    data = lazy_elemwise_func(data, transform, unsigned_dtype)
-                    if "_FillValue" in attrs:
-                        new_fill = unsigned_dtype.type(attrs["_FillValue"])
-                        attrs["_FillValue"] = new_fill
+            # Convert signed integers to unsigned when attribute is true
+            if data.dtype.kind == "i" and unsigned == "true":
+                unsigned_dtype = np.dtype("u%s" % data.dtype.itemsize)
+                transform = partial(np.asarray, dtype=unsigned_dtype)
+                data = lazy_elemwise_func(data, transform, unsigned_dtype)
+                if "_FillValue" in attrs:
+                    new_fill = unsigned_dtype.type(attrs["_FillValue"])
+                    attrs["_FillValue"] = new_fill
+
+            # Convert unsigned integers to signed when attribute is false
+            elif data.dtype.kind == "u" and unsigned == "false":
+                signed_dtype = np.dtype("i%s" % data.dtype.itemsize)
+                transform = partial(np.asarray, dtype=signed_dtype)
+                data = lazy_elemwise_func(data, transform, signed_dtype)
+                if "_FillValue" in attrs:
+                    new_fill = signed_dtype.type(attrs["_FillValue"])
+                    attrs["_FillValue"] = new_fill
+
             else:
+                # Attribute present but dtype is not integer or conversion not needed
                 warnings.warn(
                     "variable %r has _Unsigned attribute but is not "
-                    "of integer type. Ignoring attribute." % name,
+                    "of integer type or conversion not applicable. Ignoring attribute."
+                    % name,
                     SerializationWarning,
                     stacklevel=3,
                 )



######## ITEM 2-29: pydata__xarray-4966 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/xarray/coding/variables.py b/xarray/coding/variables.py
--- a/xarray/coding/variables.py
+++ b/xarray/coding/variables.py
@@ -316,6 +316,14 @@ def decode(self, variable, name=None):
                     if "_FillValue" in attrs:
                         new_fill = unsigned_dtype.type(attrs["_FillValue"])
                         attrs["_FillValue"] = new_fill
+            elif data.dtype.kind == "u":
+                if unsigned == "false":
+                    signed_dtype = np.dtype("i%s" % data.dtype.itemsize)
+                    transform = partial(np.asarray, dtype=signed_dtype)
+                    data = lazy_elemwise_func(data, transform, signed_dtype)
+                    if "_FillValue" in attrs:
+                        new_fill = signed_dtype.type(attrs["_FillValue"])
+                        attrs["_FillValue"] = new_fill
             else:
                 warnings.warn(
                     "variable %r has _Unsigned attribute but is not "

=== CANDIDATE PATCH
diff --git a/xarray/coding/variables.py b/xarray/coding/variables.py
--- a/xarray/coding/variables.py
+++ b/xarray/coding/variables.py
@@ -308,6 +308,7 @@
         if "_Unsigned" in attrs:
             unsigned = pop_to(attrs, encoding, "_Unsigned")
 
+            # Handle signed integer data marked as unsigned (CF convention)
             if data.dtype.kind == "i":
                 if unsigned == "true":
                     unsigned_dtype = np.dtype("u%s" % data.dtype.itemsize)
@@ -316,6 +317,26 @@
                     if "_FillValue" in attrs:
                         new_fill = unsigned_dtype.type(attrs["_FillValue"])
                         attrs["_FillValue"] = new_fill
+            # Handle unsigned integer data that should be interpreted as signed
+            # (OPeNDAP convention: _Unsigned=False indicates signed bytes stored as unsigned)
+            elif data.dtype.kind == "u":
+                if unsigned == "false":
+                    signed_dtype = np.dtype("i%s" % data.dtype.itemsize)
+                    transform = partial(np.asarray, dtype=signed_dtype)
+                    data = lazy_elemwise_func(data, transform, signed_dtype)
+                    if "_FillValue" in attrs:
+                        new_fill = signed_dtype.type(attrs["_FillValue"])
+                        attrs["_FillValue"] = new_fill
+                elif unsigned == "true":
+                    # Already unsigned, no action needed
+                    pass
+                else:
+                    warnings.warn(
+                        "variable %r has _Unsigned attribute with unrecognised value %r."
+                        % (name, unsigned),
+                        SerializationWarning,
+                        stacklevel=3,
+                    )
             else:
                 warnings.warn(
                     "variable %r has _Unsigned attribute but is not "



######## ITEM 2-30: pydata__xarray-4966 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/xarray/coding/variables.py b/xarray/coding/variables.py
--- a/xarray/coding/variables.py
+++ b/xarray/coding/variables.py
@@ -316,6 +316,14 @@ def decode(self, variable, name=None):
                     if "_FillValue" in attrs:
                         new_fill = unsigned_dtype.type(attrs["_FillValue"])
                         attrs["_FillValue"] = new_fill
+            elif data.dtype.kind == "u":
+                if unsigned == "false":
+                    signed_dtype = np.dtype("i%s" % data.dtype.itemsize)
+                    transform = partial(np.asarray, dtype=signed_dtype)
+                    data = lazy_elemwise_func(data, transform, signed_dtype)
+                    if "_FillValue" in attrs:
+                        new_fill = signed_dtype.type(attrs["_FillValue"])
+                        attrs["_FillValue"] = new_fill
             else:
                 warnings.warn(
                     "variable %r has _Unsigned attribute but is not "

=== CANDIDATE PATCH
diff --git a/xarray/coding/variables.py b/xarray/coding/variables.py
--- a/xarray/coding/variables.py
+++ b/xarray/coding/variables.py
@@ -316,6 +316,14 @@
                     if "_FillValue" in attrs:
                         new_fill = unsigned_dtype.type(attrs["_FillValue"])
                         attrs["_FillValue"] = new_fill
+            elif data.dtype.kind == "u" and unsigned == "false":
+                # Interpret unsigned byte data as signed, as per the OPeNDAP hack
+                signed_dtype = np.dtype("i%s" % data.dtype.itemsize)
+                transform = partial(np.asarray, dtype=signed_dtype)
+                data = lazy_elemwise_func(data, transform, signed_dtype)
+                if "_FillValue" in attrs:
+                    new_fill = signed_dtype.type(attrs["_FillValue"])
+                    attrs["_FillValue"] = new_fill
             else:
                 warnings.warn(
                     "variable %r has _Unsigned attribute but is not "



######## ITEM 2-31: pydata__xarray-6721 (gemma26 s1)
=== GOLD PATCH
diff --git a/xarray/core/common.py b/xarray/core/common.py
--- a/xarray/core/common.py
+++ b/xarray/core/common.py
@@ -2023,7 +2023,7 @@ def get_chunksizes(
 
     chunks: dict[Any, tuple[int, ...]] = {}
     for v in variables:
-        if hasattr(v.data, "chunks"):
+        if hasattr(v._data, "chunks"):
             for dim, c in v.chunksizes.items():
                 if dim in chunks and c != chunks[dim]:
                     raise ValueError(

=== CANDIDATE PATCH
diff --git a/xarray/core/common.py b/xarray/core/common.py
--- a/xarray/core/common.py
+++ b/xarray/core/common.py
@@ -2023,7 +2023,7 @@
 
     chunks: dict[Any, tuple[int, ...]] = {}
     for v in variables:
-        if hasattr(v.data, "chunks"):
+        if v.chunks is not None:
             for dim, c in v.chunksizes.items():
                 if dim in chunks and c != chunks[dim]:
                     raise ValueError(



######## ITEM 2-32: pydata__xarray-6721 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/xarray/core/common.py b/xarray/core/common.py
--- a/xarray/core/common.py
+++ b/xarray/core/common.py
@@ -2023,7 +2023,7 @@ def get_chunksizes(
 
     chunks: dict[Any, tuple[int, ...]] = {}
     for v in variables:
-        if hasattr(v.data, "chunks"):
+        if hasattr(v._data, "chunks"):
             for dim, c in v.chunksizes.items():
                 if dim in chunks and c != chunks[dim]:
                     raise ValueError(

=== CANDIDATE PATCH
diff --git a/xarray/core/common.py b/xarray/core/common.py
--- a/xarray/core/common.py
+++ b/xarray/core/common.py
@@ -2023,7 +2023,11 @@
 
     chunks: dict[Any, tuple[int, ...]] = {}
     for v in variables:
-        if hasattr(v.data, "chunks"):
+        # Use the underlying data object to avoid triggering lazy loading.
+        # Accessing ``v.data`` may materialize the array (e.g., ZarrArrayWrapper),
+        # whereas ``v._data`` holds the original array object.
+        data_obj = getattr(v, "_data", None)
+        if data_obj is not None and hasattr(data_obj, "chunks"):
             for dim, c in v.chunksizes.items():
                 if dim in chunks and c != chunks[dim]:
                     raise ValueError(



######## ITEM 2-33: pydata__xarray-6721 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/xarray/core/common.py b/xarray/core/common.py
--- a/xarray/core/common.py
+++ b/xarray/core/common.py
@@ -2023,7 +2023,7 @@ def get_chunksizes(
 
     chunks: dict[Any, tuple[int, ...]] = {}
     for v in variables:
-        if hasattr(v.data, "chunks"):
+        if hasattr(v._data, "chunks"):
             for dim, c in v.chunksizes.items():
                 if dim in chunks and c != chunks[dim]:
                     raise ValueError(

=== CANDIDATE PATCH
diff --git a/xarray/core/common.py b/xarray/core/common.py
--- a/xarray/core/common.py
+++ b/xarray/core/common.py
@@ -2023,7 +2023,8 @@
 
     chunks: dict[Any, tuple[int, ...]] = {}
     for v in variables:
-        if hasattr(v.data, "chunks"):
+        # Inspect the underlying array object directly to avoid triggering lazy loading.
+        if hasattr(v._data, "chunks"):
             for dim, c in v.chunksizes.items():
                 if dim in chunks and c != chunks[dim]:
                     raise ValueError(



######## ITEM 2-34: pydata__xarray-6721 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/xarray/core/common.py b/xarray/core/common.py
--- a/xarray/core/common.py
+++ b/xarray/core/common.py
@@ -2023,7 +2023,7 @@ def get_chunksizes(
 
     chunks: dict[Any, tuple[int, ...]] = {}
     for v in variables:
-        if hasattr(v.data, "chunks"):
+        if hasattr(v._data, "chunks"):
             for dim, c in v.chunksizes.items():
                 if dim in chunks and c != chunks[dim]:
                     raise ValueError(

=== CANDIDATE PATCH
diff --git a/xarray/core/common.py b/xarray/core/common.py
--- a/xarray/core/common.py
+++ b/xarray/core/common.py
@@ -2021,9 +2021,18 @@
     variables: Iterable[Variable],
 ) -> Mapping[Any, tuple[int, ...]]:
 
+    # NOTE: ``Variable.data`` may trigger loading of the full array (e.g. for Zarr
+    # backends).  To avoid unnecessary memory use we inspect the underlying data
+    # object directly via ``Variable._data`` when possible.  This attribute holds
+    # the lazy array without materialising it.
     chunks: dict[Any, tuple[int, ...]] = {}
     for v in variables:
-        if hasattr(v.data, "chunks"):
+        # Prefer the internal ``_data`` attribute to avoid invoking ``Variable.data``
+        data_obj = getattr(v, "_data", None)
+        if data_obj is None:
+            # Fallback to ``v.data`` only if ``_data`` is not available (unlikely)
+            data_obj = v.data
+        if hasattr(data_obj, "chunks"):
             for dim, c in v.chunksizes.items():
                 if dim in chunks and c != chunks[dim]:
                     raise ValueError(



######## ITEM 2-35: pylint-dev__pylint-7277 (gemma26 s0)
=== GOLD PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -96,9 +96,10 @@ def modify_sys_path() -> None:
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
-    env_pythonpath = os.environ.get("PYTHONPATH", "")
     cwd = os.getcwd()
+    if sys.path[0] in ("", ".", cwd):
+        sys.path.pop(0)
+    env_pythonpath = os.environ.get("PYTHONPATH", "")
     if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
         sys.path.pop(0)
     elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):

=== CANDIDATE PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -86,7 +86,7 @@
     stdlib or pylint's own modules.
     CPython issue: https://bugs.python.org/issue33053
 
-    - Remove the first entry. This will always be either "" or the working directory
+    - Remove the first entry if it is "" or the working directory.
     - Remove the working directory from the second and third entries
       if PYTHONPATH includes a ":" at the beginning or the end.
       https://github.com/PyCQA/pylint/issues/3636
@@ -96,7 +96,9 @@
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
+    cwd = os.getcwd()
+    if sys.path[0] in ("", ".", cwd):
+        sys.path.pop(0)
     env_pythonpath = os.environ.get("PYTHONPATH", "")
     cwd = os.getcwd()
     if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):



######## ITEM 2-36: pylint-dev__pylint-7277 (gemma26 s1)
=== GOLD PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -96,9 +96,10 @@ def modify_sys_path() -> None:
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
-    env_pythonpath = os.environ.get("PYTHONPATH", "")
     cwd = os.getcwd()
+    if sys.path[0] in ("", ".", cwd):
+        sys.path.pop(0)
+    env_pythonpath = os.environ.get("PYTHONPATH", "")
     if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
         sys.path.pop(0)
     elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):

=== CANDIDATE PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -86,7 +86,7 @@
     stdlib or pylint's own modules.
     CPython issue: https://bugs.python.org/issue33053
 
-    - Remove the first entry. This will always be either "" or the working directory
+    - Remove the first entry if it is "" or the working directory.
     - Remove the working directory from the second and third entries
       if PYTHONPATH includes a ":" at the beginning or the end.
       https://github.com/PyCQA/pylint/issues/3636
@@ -96,7 +96,10 @@
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
+    cwd = os.getcwd()
+    if sys.path and sys.path[0] in ("", ".", cwd):
+        sys.path.pop(0)
+
     env_pythonpath = os.environ.get("PYTHONPATH", "")
     cwd = os.getcwd()
     if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):



######## ITEM 2-37: pylint-dev__pylint-7277 (gemma26 s2)
=== GOLD PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -96,9 +96,10 @@ def modify_sys_path() -> None:
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
-    env_pythonpath = os.environ.get("PYTHONPATH", "")
     cwd = os.getcwd()
+    if sys.path[0] in ("", ".", cwd):
+        sys.path.pop(0)
+    env_pythonpath = os.environ.get("PYTHONPATH", "")
     if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
         sys.path.pop(0)
     elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):

=== CANDIDATE PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -86,7 +86,7 @@
     stdlib or pylint's own modules.
     CPython issue: https://bugs.python.org/issue33053
 
-    - Remove the first entry. This will always be either "" or the working directory
+    - Remove the first entry if it is "" or the working directory
     - Remove the working directory from the second and third entries
       if PYTHONPATH includes a ":" at the beginning or the end.
       https://github.com/PyCQA/pylint/issues/3636
@@ -96,7 +96,9 @@
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
+    cwd = os.getcwd()
+    if sys.path[0] in ("", ".", cwd):
+        sys.path.pop(0)
     env_pythonpath = os.environ.get("PYTHONPATH", "")
     cwd = os.getcwd()
     if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):



######## ITEM 2-38: pylint-dev__pylint-7277 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -96,9 +96,10 @@ def modify_sys_path() -> None:
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
-    env_pythonpath = os.environ.get("PYTHONPATH", "")
     cwd = os.getcwd()
+    if sys.path[0] in ("", ".", cwd):
+        sys.path.pop(0)
+    env_pythonpath = os.environ.get("PYTHONPATH", "")
     if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
         sys.path.pop(0)
     elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):

=== CANDIDATE PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -96,9 +96,14 @@
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
+    cwd = os.getcwd()
+    # Remove the first entry only if it points to the current working directory
+    # or is an empty string / "." (the typical representation of the cwd).
+    if sys.path:
+        first_entry = sys.path[0]
+        if first_entry in ("", ".", cwd):
+            sys.path.pop(0)
     env_pythonpath = os.environ.get("PYTHONPATH", "")
-    cwd = os.getcwd()
     if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
         sys.path.pop(0)
     elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):



######## ITEM 2-39: pylint-dev__pylint-7277 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -96,9 +96,10 @@ def modify_sys_path() -> None:
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
-    env_pythonpath = os.environ.get("PYTHONPATH", "")
     cwd = os.getcwd()
+    if sys.path[0] in ("", ".", cwd):
+        sys.path.pop(0)
+    env_pythonpath = os.environ.get("PYTHONPATH", "")
     if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
         sys.path.pop(0)
     elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):

=== CANDIDATE PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -96,7 +96,11 @@
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
+    # Remove the first entry only if it represents the current working directory
+    # or an empty path ("" or ".").
+    first_entry = sys.path[0] if sys.path else None
+    if first_entry in ("", ".", os.getcwd()):
+        sys.path.pop(0)
     env_pythonpath = os.environ.get("PYTHONPATH", "")
     cwd = os.getcwd()
     if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):



######## ITEM 2-40: pylint-dev__pylint-7277 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -96,9 +96,10 @@ def modify_sys_path() -> None:
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
-    env_pythonpath = os.environ.get("PYTHONPATH", "")
     cwd = os.getcwd()
+    if sys.path[0] in ("", ".", cwd):
+        sys.path.pop(0)
+    env_pythonpath = os.environ.get("PYTHONPATH", "")
     if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
         sys.path.pop(0)
     elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):

=== CANDIDATE PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -96,13 +96,15 @@
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
-    env_pythonpath = os.environ.get("PYTHONPATH", "")
+    first = sys.path[0]
     cwd = os.getcwd()
-    if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
+    if first in ("", ".", cwd):
         sys.path.pop(0)
-    elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):
-        sys.path.pop(1)
+        env_pythonpath = os.environ.get("PYTHONPATH", "")
+        if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
+            sys.path.pop(0)
+        elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):
+            sys.path.pop(1)
 
 
 version = __version__



######## ITEM 2-41: pylint-dev__pylint-7277 (gpt-oss-20b s2)
=== GOLD PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -96,9 +96,10 @@ def modify_sys_path() -> None:
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
-    env_pythonpath = os.environ.get("PYTHONPATH", "")
     cwd = os.getcwd()
+    if sys.path[0] in ("", ".", cwd):
+        sys.path.pop(0)
+    env_pythonpath = os.environ.get("PYTHONPATH", "")
     if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
         sys.path.pop(0)
     elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):

=== CANDIDATE PATCH
diff --git a/pylint/__init__.py b/pylint/__init__.py
--- a/pylint/__init__.py
+++ b/pylint/__init__.py
@@ -96,13 +96,21 @@
       if pylint is installed in an editable configuration (as the last item).
       https://github.com/PyCQA/pylint/issues/4161
     """
-    sys.path.pop(0)
+    # Remove the first entry only if it is the current working directory,
+    # an empty string, or a single dot.
+    first = sys.path[0]
+    removed_first = False
+    if first in ("", ".", os.getcwd()):
+        sys.path.pop(0)
+        removed_first = True
+
     env_pythonpath = os.environ.get("PYTHONPATH", "")
     cwd = os.getcwd()
-    if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
-        sys.path.pop(0)
-    elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):
-        sys.path.pop(1)
+    if removed_first:
+        if env_pythonpath.startswith(":") and env_pythonpath not in (f":{cwd}", ":."):
+            sys.path.pop(0)
+        elif env_pythonpath.endswith(":") and env_pythonpath not in (f"{cwd}:", ".:"):
+            sys.path.pop(1)
 
 
 version = __version__



######## ITEM 2-42: pytest-dev__pytest-5262 (gpt-oss-120b s0)
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
@@ -449,6 +449,20 @@
 
     def __getattr__(self, name):
         return getattr(object.__getattribute__(self, "buffer"), name)
+
+    @property
+    def mode(self):
+        """Return the underlying buffer's mode without the binary flag.
+
+        This makes ``EncodedFile`` appear as a text file to libraries (e.g.
+        youtube‑dl) that inspect ``.mode`` for a ``'b'`` character to decide
+        whether to write bytes.  The underlying buffer may be opened in binary
+        mode (e.g. ``'rb+'``), but exposing a mode without ``'b'`` avoids the
+        ``TypeError`` raised by :meth:`write` when bytes are passed.
+        """
+        m = getattr(self.buffer, "mode", "")
+        # Strip the binary flag while preserving other mode characters
+        return m.replace("b", "")
 
 
 CaptureResult = collections.namedtuple("CaptureResult", ["out", "err"])



######## ITEM 2-43: pytest-dev__pytest-5262 (gpt-oss-120b s1)
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
@@ -446,6 +446,12 @@
     def name(self):
         """Ensure that file.name is a string."""
         return repr(self.buffer)
+
+    @property
+    def mode(self):
+        """Return the underlying file mode without the binary flag."""
+        m = getattr(self.buffer, "mode", "")
+        return m.replace("b", "")
 
     def __getattr__(self, name):
         return getattr(object.__getattribute__(self, "buffer"), name)

