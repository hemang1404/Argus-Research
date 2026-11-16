

######## ITEM 1-0: django__django-13933 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/django/forms/models.py b/django/forms/models.py
--- a/django/forms/models.py
+++ b/django/forms/models.py
@@ -1284,7 +1284,11 @@ def to_python(self, value):
                 value = getattr(value, key)
             value = self.queryset.get(**{key: value})
         except (ValueError, TypeError, self.queryset.model.DoesNotExist):
-            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')
+            raise ValidationError(
+                self.error_messages['invalid_choice'],
+                code='invalid_choice',
+                params={'value': value},
+            )
         return value
 
     def validate(self, value):

=== CANDIDATE PATCH
diff --git a/django/forms/models.py b/django/forms/models.py
--- a/django/forms/models.py
+++ b/django/forms/models.py
@@ -1188,7 +1188,7 @@
     # This class is a subclass of ChoiceField for purity, but it doesn't
     # actually use any of ChoiceField's implementation.
     default_error_messages = {
-        'invalid_choice': _('Select a valid choice. That choice is not one of'
+        'invalid_choice': _('Select a valid choice. %(value)s is not one of'
                             ' the available choices.'),
     }
     iterator = ModelChoiceIterator
@@ -1284,7 +1284,11 @@
                 value = getattr(value, key)
             value = self.queryset.get(**{key: value})
         except (ValueError, TypeError, self.queryset.model.DoesNotExist):
-            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')
+            raise ValidationError(
+                self.error_messages['invalid_choice'],
+                code='invalid_choice',
+                params={'value': value},
+            )
         return value
 
     def validate(self, value):



######## ITEM 1-1: django__django-13933 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/django/forms/models.py b/django/forms/models.py
--- a/django/forms/models.py
+++ b/django/forms/models.py
@@ -1284,7 +1284,11 @@ def to_python(self, value):
                 value = getattr(value, key)
             value = self.queryset.get(**{key: value})
         except (ValueError, TypeError, self.queryset.model.DoesNotExist):
-            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')
+            raise ValidationError(
+                self.error_messages['invalid_choice'],
+                code='invalid_choice',
+                params={'value': value},
+            )
         return value
 
     def validate(self, value):

=== CANDIDATE PATCH
diff --git a/django/forms/models.py b/django/forms/models.py
--- a/django/forms/models.py
+++ b/django/forms/models.py
@@ -1188,8 +1188,7 @@
     # This class is a subclass of ChoiceField for purity, but it doesn't
     # actually use any of ChoiceField's implementation.
     default_error_messages = {
-        'invalid_choice': _('Select a valid choice. That choice is not one of'
-                            ' the available choices.'),
+        'invalid_choice': _('Select a valid choice. %(value)s is not one of the available choices.'),
     }
     iterator = ModelChoiceIterator
 
@@ -1284,7 +1283,11 @@
                 value = getattr(value, key)
             value = self.queryset.get(**{key: value})
         except (ValueError, TypeError, self.queryset.model.DoesNotExist):
-            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')
+            raise ValidationError(
+                self.error_messages['invalid_choice'],
+                code='invalid_choice',
+                params={'value': value},
+            )
         return value
 
     def validate(self, value):



######## ITEM 1-2: django__django-13933 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/django/forms/models.py b/django/forms/models.py
--- a/django/forms/models.py
+++ b/django/forms/models.py
@@ -1284,7 +1284,11 @@ def to_python(self, value):
                 value = getattr(value, key)
             value = self.queryset.get(**{key: value})
         except (ValueError, TypeError, self.queryset.model.DoesNotExist):
-            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')
+            raise ValidationError(
+                self.error_messages['invalid_choice'],
+                code='invalid_choice',
+                params={'value': value},
+            )
         return value
 
     def validate(self, value):

=== CANDIDATE PATCH
diff --git a/django/forms/models.py b/django/forms/models.py
--- a/django/forms/models.py
+++ b/django/forms/models.py
@@ -1278,13 +1278,14 @@
     def to_python(self, value):
         if value in self.empty_values:
             return None
+        orig_value = value
         try:
             key = self.to_field_name or 'pk'
             if isinstance(value, self.queryset.model):
                 value = getattr(value, key)
             value = self.queryset.get(**{key: value})
         except (ValueError, TypeError, self.queryset.model.DoesNotExist):
-            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')
+            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice', params={'value': orig_value})
         return value
 
     def validate(self, value):



######## ITEM 1-3: django__django-13933 (gpt-oss-20b s2)
=== GOLD PATCH
diff --git a/django/forms/models.py b/django/forms/models.py
--- a/django/forms/models.py
+++ b/django/forms/models.py
@@ -1284,7 +1284,11 @@ def to_python(self, value):
                 value = getattr(value, key)
             value = self.queryset.get(**{key: value})
         except (ValueError, TypeError, self.queryset.model.DoesNotExist):
-            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')
+            raise ValidationError(
+                self.error_messages['invalid_choice'],
+                code='invalid_choice',
+                params={'value': value},
+            )
         return value
 
     def validate(self, value):

=== CANDIDATE PATCH
diff --git a/django/forms/models.py b/django/forms/models.py
--- a/django/forms/models.py
+++ b/django/forms/models.py
@@ -1188,8 +1188,7 @@
     # This class is a subclass of ChoiceField for purity, but it doesn't
     # actually use any of ChoiceField's implementation.
     default_error_messages = {
-        'invalid_choice': _('Select a valid choice. That choice is not one of'
-                            ' the available choices.'),
+        'invalid_choice': _('Select a valid choice. %(value)s is not one of the available choices.'),
     }
     iterator = ModelChoiceIterator
 
@@ -1284,7 +1283,7 @@
                 value = getattr(value, key)
             value = self.queryset.get(**{key: value})
         except (ValueError, TypeError, self.queryset.model.DoesNotExist):
-            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice')
+            raise ValidationError(self.error_messages['invalid_choice'], code='invalid_choice', params={'value': value})
         return value
 
     def validate(self, value):



######## ITEM 1-4: django__django-14238 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/django/db/models/fields/__init__.py b/django/db/models/fields/__init__.py
--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -2524,7 +2524,7 @@ def __instancecheck__(self, instance):
         return isinstance(instance, self._subclasses) or super().__instancecheck__(instance)
 
     def __subclasscheck__(self, subclass):
-        return subclass in self._subclasses or super().__subclasscheck__(subclass)
+        return issubclass(subclass, self._subclasses) or super().__subclasscheck__(subclass)
 
 
 class AutoField(AutoFieldMixin, IntegerField, metaclass=AutoFieldMeta):

=== CANDIDATE PATCH
diff --git a/django/db/models/fields/__init__.py b/django/db/models/fields/__init__.py
--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -2524,7 +2524,10 @@
         return isinstance(instance, self._subclasses) or super().__instancecheck__(instance)
 
     def __subclasscheck__(self, subclass):
-        return subclass in self._subclasses or super().__subclasscheck__(subclass)
+        # Allow subclasses of BigAutoField and SmallAutoField to be recognized as
+        # AutoField subclasses. This ensures that custom fields inheriting from
+        # those classes satisfy the DEFAULT_AUTO_FIELD check.
+        return any(issubclass(subclass, cls) for cls in self._subclasses) or super().__subclasscheck__(subclass)
 
 
 class AutoField(AutoFieldMixin, IntegerField, metaclass=AutoFieldMeta):



######## ITEM 1-5: django__django-14238 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/django/db/models/fields/__init__.py b/django/db/models/fields/__init__.py
--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -2524,7 +2524,7 @@ def __instancecheck__(self, instance):
         return isinstance(instance, self._subclasses) or super().__instancecheck__(instance)
 
     def __subclasscheck__(self, subclass):
-        return subclass in self._subclasses or super().__subclasscheck__(subclass)
+        return issubclass(subclass, self._subclasses) or super().__subclasscheck__(subclass)
 
 
 class AutoField(AutoFieldMixin, IntegerField, metaclass=AutoFieldMeta):

=== CANDIDATE PATCH
diff --git a/django/db/models/fields/__init__.py b/django/db/models/fields/__init__.py
--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -2524,7 +2524,17 @@
         return isinstance(instance, self._subclasses) or super().__instancecheck__(instance)
 
     def __subclasscheck__(self, subclass):
-        return subclass in self._subclasses or super().__subclasscheck__(subclass)
+        """
+        Return True if ``subclass`` is a subclass of any class listed in
+        ``_subclasses`` (i.e. ``BigAutoField`` or ``SmallAutoField``) or if the
+        normal ``type.__subclasscheck__`` logic applies. This allows custom
+        fields that inherit from ``BigAutoField`` or ``SmallAutoField`` to be
+        recognised as valid ``AutoField`` subclasses (e.g. for
+        ``DEFAULT_AUTO_FIELD`` handling).
+        """
+        return any(
+            issubclass(subclass, candidate) for candidate in self._subclasses
+        ) or super().__subclasscheck__(subclass)
 
 
 class AutoField(AutoFieldMixin, IntegerField, metaclass=AutoFieldMeta):



######## ITEM 1-6: django__django-14238 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/django/db/models/fields/__init__.py b/django/db/models/fields/__init__.py
--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -2524,7 +2524,7 @@ def __instancecheck__(self, instance):
         return isinstance(instance, self._subclasses) or super().__instancecheck__(instance)
 
     def __subclasscheck__(self, subclass):
-        return subclass in self._subclasses or super().__subclasscheck__(subclass)
+        return issubclass(subclass, self._subclasses) or super().__subclasscheck__(subclass)
 
 
 class AutoField(AutoFieldMixin, IntegerField, metaclass=AutoFieldMeta):

=== CANDIDATE PATCH
diff --git a/django/db/models/fields/__init__.py b/django/db/models/fields/__init__.py
--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -2524,7 +2524,8 @@
         return isinstance(instance, self._subclasses) or super().__instancecheck__(instance)
 
     def __subclasscheck__(self, subclass):
-        return subclass in self._subclasses or super().__subclasscheck__(subclass)
+        # Allow subclasses of the recognized auto field types.
+        return any(issubclass(subclass, cls) for cls in self._subclasses) or super().__subclasscheck__(subclass)
 
 
 class AutoField(AutoFieldMixin, IntegerField, metaclass=AutoFieldMeta):



######## ITEM 1-7: django__django-14238 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/django/db/models/fields/__init__.py b/django/db/models/fields/__init__.py
--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -2524,7 +2524,7 @@ def __instancecheck__(self, instance):
         return isinstance(instance, self._subclasses) or super().__instancecheck__(instance)
 
     def __subclasscheck__(self, subclass):
-        return subclass in self._subclasses or super().__subclasscheck__(subclass)
+        return issubclass(subclass, self._subclasses) or super().__subclasscheck__(subclass)
 
 
 class AutoField(AutoFieldMixin, IntegerField, metaclass=AutoFieldMeta):

=== CANDIDATE PATCH
diff --git a/django/db/models/fields/__init__.py b/django/db/models/fields/__init__.py
--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -2524,7 +2524,13 @@
         return isinstance(instance, self._subclasses) or super().__instancecheck__(instance)
 
     def __subclasscheck__(self, subclass):
-        return subclass in self._subclasses or super().__subclasscheck__(subclass)
+        # Include subclasses of BigAutoField and SmallAutoField in the
+        # subclass check. This allows custom fields that inherit from
+        # BigAutoField or SmallAutoField to be considered subclasses of
+        # AutoField for the DEFAULT_AUTO_FIELD validation.
+        if isinstance(subclass, type) and issubclass(subclass, (BigAutoField, SmallAutoField)):
+            return True
+        return super().__subclasscheck__(subclass)
 
 
 class AutoField(AutoFieldMixin, IntegerField, metaclass=AutoFieldMeta):



######## ITEM 1-8: django__django-14434 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/django/db/backends/base/schema.py b/django/db/backends/base/schema.py
--- a/django/db/backends/base/schema.py
+++ b/django/db/backends/base/schema.py
@@ -1241,9 +1241,9 @@ def create_unique_name(*args, **kwargs):
             return self.quote_name(self._create_index_name(*args, **kwargs))
 
         compiler = Query(model, alias_cols=False).get_compiler(connection=self.connection)
-        table = Table(model._meta.db_table, self.quote_name)
+        table = model._meta.db_table
         if name is None:
-            name = IndexName(model._meta.db_table, columns, '_uniq', create_unique_name)
+            name = IndexName(table, columns, '_uniq', create_unique_name)
         else:
             name = self.quote_name(name)
         if condition or include or opclasses or expressions:
@@ -1253,10 +1253,10 @@ def create_unique_name(*args, **kwargs):
         if columns:
             columns = self._index_columns(table, columns, col_suffixes=(), opclasses=opclasses)
         else:
-            columns = Expressions(model._meta.db_table, expressions, compiler, self.quote_value)
+            columns = Expressions(table, expressions, compiler, self.quote_value)
         return Statement(
             sql,
-            table=table,
+            table=Table(table, self.quote_name),
             name=name,
             columns=columns,
             condition=self._index_condition_sql(condition),

=== CANDIDATE PATCH
diff --git a/django/db/backends/base/schema.py b/django/db/backends/base/schema.py
--- a/django/db/backends/base/schema.py
+++ b/django/db/backends/base/schema.py
@@ -1251,7 +1251,9 @@
         else:
             sql = self.sql_create_unique
         if columns:
-            columns = self._index_columns(table, columns, col_suffixes=(), opclasses=opclasses)
+            # Use the table name string (not a Table instance) when constructing
+            # the Columns reference, so that `references_column` is detected correctly.
+            columns = self._index_columns(model._meta.db_table, columns, col_suffixes=(), opclasses=opclasses)
         else:
             columns = Expressions(model._meta.db_table, expressions, compiler, self.quote_value)
         return Statement(



######## ITEM 1-9: django__django-14771 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/django/utils/autoreload.py b/django/utils/autoreload.py
--- a/django/utils/autoreload.py
+++ b/django/utils/autoreload.py
@@ -220,6 +220,11 @@ def get_child_arguments():
     py_script = Path(sys.argv[0])
 
     args = [sys.executable] + ['-W%s' % o for o in sys.warnoptions]
+    if sys.implementation.name == 'cpython':
+        args.extend(
+            f'-X{key}' if value is True else f'-X{key}={value}'
+            for key, value in sys._xoptions.items()
+        )
     # __spec__ is set when the server was started with the `-m` option,
     # see https://docs.python.org/3/reference/import.html#main-spec
     # __spec__ may not exist, e.g. when running in a Conda env.

=== CANDIDATE PATCH
diff --git a/django/utils/autoreload.py b/django/utils/autoreload.py
--- a/django/utils/autoreload.py
+++ b/django/utils/autoreload.py
@@ -220,6 +220,13 @@
     py_script = Path(sys.argv[0])
 
     args = [sys.executable] + ['-W%s' % o for o in sys.warnoptions]
+    # Pass through any -X options (cpython implementation) to the child process.
+    # sys._xoptions is a dict mapping option names to either True or a value.
+    for opt, val in getattr(sys, "_xoptions", {}).items():
+        if val is True:
+            args.append(f'-X{opt}')
+        else:
+            args.append(f'-X{opt}={val}')
     # __spec__ is set when the server was started with the `-m` option,
     # see https://docs.python.org/3/reference/import.html#main-spec
     # __spec__ may not exist, e.g. when running in a Conda env.



######## ITEM 1-10: django__django-15315 (gemma26 s2)
=== GOLD PATCH
diff --git a/django/db/models/fields/__init__.py b/django/db/models/fields/__init__.py
--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -542,11 +542,7 @@ def __lt__(self, other):
         return NotImplemented
 
     def __hash__(self):
-        return hash((
-            self.creation_counter,
-            self.model._meta.app_label if hasattr(self, 'model') else None,
-            self.model._meta.model_name if hasattr(self, 'model') else None,
-        ))
+        return hash(self.creation_counter)
 
     def __deepcopy__(self, memodict):
         # We don't have to deepcopy very much here, since most things are not

=== CANDIDATE PATCH
diff --git a/django/db/models/fields/__init__.py b/django/db/models/fields/__init__.py
--- a/django/db/models/fields/__init__.py
+++ b/django/db/models/fields/__init__.py
@@ -587,6 +587,18 @@
         return _load_field, (self.model._meta.app_label, self.model._meta.object_name,
                              self.name)
 
+    def __hash__(self):
+        return id(self)
+
+    def __hash__(self):
+        return id(self)
+
+    def __hash__(self):
+        return id(self)
+
+    def __hash__(self):
+        return id(self)
+
     def get_pk_value_on_save(self, instance):
         """
         Hook to generate new PK values on save. This method is called when



######## ITEM 1-11: django__django-15382 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/django/db/models/expressions.py b/django/db/models/expressions.py
--- a/django/db/models/expressions.py
+++ b/django/db/models/expressions.py
@@ -1211,13 +1211,18 @@ def __invert__(self):
 
     def as_sql(self, compiler, connection, template=None, **extra_context):
         query = self.query.exists(using=connection.alias)
-        sql, params = super().as_sql(
-            compiler,
-            connection,
-            template=template,
-            query=query,
-            **extra_context,
-        )
+        try:
+            sql, params = super().as_sql(
+                compiler,
+                connection,
+                template=template,
+                query=query,
+                **extra_context,
+            )
+        except EmptyResultSet:
+            if self.negated:
+                return '', ()
+            raise
         if self.negated:
             sql = 'NOT {}'.format(sql)
         return sql, params

=== CANDIDATE PATCH
diff --git a/django/db/models/expressions.py b/django/db/models/expressions.py
--- a/django/db/models/expressions.py
+++ b/django/db/models/expressions.py
@@ -1210,14 +1210,27 @@
         return clone
 
     def as_sql(self, compiler, connection, template=None, **extra_context):
-        query = self.query.exists(using=connection.alias)
-        sql, params = super().as_sql(
-            compiler,
-            connection,
-            template=template,
-            query=query,
-            **extra_context,
-        )
+        """
+        Compile the EXISTS subquery. If the subquery would raise an
+        EmptyResultSet (e.g. when the inner queryset is empty), treat it as
+        a constant FALSE (or TRUE when negated) so that other filter
+        conditions are not discarded.
+        """
+        try:
+            query = self.query.exists(using=connection.alias)
+            sql, params = super().as_sql(
+                compiler,
+                connection,
+                template=template,
+                query=query,
+                **extra_context,
+            )
+        except EmptyResultSet:
+            # An empty subquery means EXISTS evaluates to FALSE.
+            # Use a Value expression to represent this constant.
+            from .expressions import Value  # local import to avoid circularity
+            const_expr = Value(False, output_field=self.output_field)
+            sql, params = const_expr.as_sql(compiler, connection)
         if self.negated:
             sql = 'NOT {}'.format(sql)
         return sql, params



######## ITEM 1-12: django__django-15382 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/django/db/models/expressions.py b/django/db/models/expressions.py
--- a/django/db/models/expressions.py
+++ b/django/db/models/expressions.py
@@ -1211,13 +1211,18 @@ def __invert__(self):
 
     def as_sql(self, compiler, connection, template=None, **extra_context):
         query = self.query.exists(using=connection.alias)
-        sql, params = super().as_sql(
-            compiler,
-            connection,
-            template=template,
-            query=query,
-            **extra_context,
-        )
+        try:
+            sql, params = super().as_sql(
+                compiler,
+                connection,
+                template=template,
+                query=query,
+                **extra_context,
+            )
+        except EmptyResultSet:
+            if self.negated:
+                return '', ()
+            raise
         if self.negated:
             sql = 'NOT {}'.format(sql)
         return sql, params

=== CANDIDATE PATCH
diff --git a/django/db/models/expressions.py b/django/db/models/expressions.py
--- a/django/db/models/expressions.py
+++ b/django/db/models/expressions.py
@@ -1211,13 +1211,17 @@
 
     def as_sql(self, compiler, connection, template=None, **extra_context):
         query = self.query.exists(using=connection.alias)
-        sql, params = super().as_sql(
-            compiler,
-            connection,
-            template=template,
-            query=query,
-            **extra_context,
-        )
+        try:
+            sql, params = super().as_sql(
+                compiler,
+                connection,
+                template=template,
+                query=query,
+                **extra_context,
+            )
+        except EmptyResultSet:
+            # An EXISTS on an empty queryset evaluates to False.
+            sql, params = compiler.compile(Value(False))
         if self.negated:
             sql = 'NOT {}'.format(sql)
         return sql, params



######## ITEM 1-13: django__django-15382 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/django/db/models/expressions.py b/django/db/models/expressions.py
--- a/django/db/models/expressions.py
+++ b/django/db/models/expressions.py
@@ -1211,13 +1211,18 @@ def __invert__(self):
 
     def as_sql(self, compiler, connection, template=None, **extra_context):
         query = self.query.exists(using=connection.alias)
-        sql, params = super().as_sql(
-            compiler,
-            connection,
-            template=template,
-            query=query,
-            **extra_context,
-        )
+        try:
+            sql, params = super().as_sql(
+                compiler,
+                connection,
+                template=template,
+                query=query,
+                **extra_context,
+            )
+        except EmptyResultSet:
+            if self.negated:
+                return '', ()
+            raise
         if self.negated:
             sql = 'NOT {}'.format(sql)
         return sql, params

=== CANDIDATE PATCH
diff --git a/django/db/models/expressions.py b/django/db/models/expressions.py
--- a/django/db/models/expressions.py
+++ b/django/db/models/expressions.py
@@ -1211,13 +1211,20 @@
 
     def as_sql(self, compiler, connection, template=None, **extra_context):
         query = self.query.exists(using=connection.alias)
-        sql, params = super().as_sql(
-            compiler,
-            connection,
-            template=template,
-            query=query,
-            **extra_context,
-        )
+        try:
+            sql, params = super().as_sql(
+                compiler,
+                connection,
+                template=template,
+                query=query,
+                **extra_context,
+            )
+        except EmptyResultSet:
+            # Empty subquery: EXISTS is always False; NOT EXISTS is always True
+            if self.negated:
+                return '1=1', []
+            else:
+                return '1=0', []
         if self.negated:
             sql = 'NOT {}'.format(sql)
         return sql, params



######## ITEM 1-14: django__django-15930 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/django/db/models/expressions.py b/django/db/models/expressions.py
--- a/django/db/models/expressions.py
+++ b/django/db/models/expressions.py
@@ -1299,6 +1299,11 @@ def as_sql(self, compiler, connection, template=None, **extra_context):
         template_params = extra_context
         sql_params = []
         condition_sql, condition_params = compiler.compile(self.condition)
+        # Filters that match everything are handled as empty strings in the
+        # WHERE clause, but in a CASE WHEN expression they must use a predicate
+        # that's always True.
+        if condition_sql == "":
+            condition_sql, condition_params = compiler.compile(Value(True))
         template_params["condition"] = condition_sql
         sql_params.extend(condition_params)
         result_sql, result_params = compiler.compile(self.result)

=== CANDIDATE PATCH
diff --git a/django/db/models/expressions.py b/django/db/models/expressions.py
--- a/django/db/models/expressions.py
+++ b/django/db/models/expressions.py
@@ -1388,6 +1388,14 @@
                 case_sql, case_params = compiler.compile(case)
             except EmptyResultSet:
                 continue
+            # If the compiled case has an empty condition (e.g., from a negated
+            # empty ``Q(pk__in=[])``), the SQL looks like ``WHEN THEN`` which is
+            # invalid. Replace the empty condition with a tautology.
+            if case_sql.strip().startswith("WHEN") and "THEN" in case_sql:
+                before, after = case_sql.split("THEN", 1)
+                condition = before[len("WHEN"):].strip()
+                if not condition:
+                    case_sql = f"WHEN 1=1 THEN{after}"
             case_parts.append(case_sql)
             sql_params.extend(case_params)
         default_sql, default_params = compiler.compile(self.default)



######## ITEM 1-15: django__django-15930 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/django/db/models/expressions.py b/django/db/models/expressions.py
--- a/django/db/models/expressions.py
+++ b/django/db/models/expressions.py
@@ -1299,6 +1299,11 @@ def as_sql(self, compiler, connection, template=None, **extra_context):
         template_params = extra_context
         sql_params = []
         condition_sql, condition_params = compiler.compile(self.condition)
+        # Filters that match everything are handled as empty strings in the
+        # WHERE clause, but in a CASE WHEN expression they must use a predicate
+        # that's always True.
+        if condition_sql == "":
+            condition_sql, condition_params = compiler.compile(Value(True))
         template_params["condition"] = condition_sql
         sql_params.extend(condition_params)
         result_sql, result_params = compiler.compile(self.result)

=== CANDIDATE PATCH
diff --git a/django/db/models/expressions.py b/django/db/models/expressions.py
--- a/django/db/models/expressions.py
+++ b/django/db/models/expressions.py
@@ -1385,9 +1385,20 @@
         sql_params = []
         for case in self.cases:
             try:
-                case_sql, case_params = compiler.compile(case)
+                # Compile the condition and result separately to handle empty conditions
+                cond_sql, cond_params = compiler.compile(case.condition)
             except EmptyResultSet:
                 continue
+            try:
+                result_sql, result_params = compiler.compile(case.result)
+            except EmptyResultSet:
+                # If result can't be compiled, skip this case
+                continue
+            # If the condition compiles to an empty string, use a default always-true condition
+            if not cond_sql.strip():
+                cond_sql = "1=1"
+            case_sql = f"WHEN {cond_sql} THEN {result_sql}"
+            case_params = cond_params + result_params
             case_parts.append(case_sql)
             sql_params.extend(case_params)
         default_sql, default_params = compiler.compile(self.default)



######## ITEM 1-16: django__django-16116 (gemma26 s0)
=== GOLD PATCH
diff --git a/django/core/management/commands/makemigrations.py b/django/core/management/commands/makemigrations.py
--- a/django/core/management/commands/makemigrations.py
+++ b/django/core/management/commands/makemigrations.py
@@ -70,7 +70,10 @@ def add_arguments(self, parser):
             "--check",
             action="store_true",
             dest="check_changes",
-            help="Exit with a non-zero status if model changes are missing migrations.",
+            help=(
+                "Exit with a non-zero status if model changes are missing migrations "
+                "and don't actually write them."
+            ),
         )
         parser.add_argument(
             "--scriptable",
@@ -248,12 +251,12 @@ def handle(self, *app_labels, **options):
                 else:
                     self.log("No changes detected")
         else:
+            if check_changes:
+                sys.exit(1)
             if self.update:
                 self.write_to_last_migration_files(changes)
             else:
                 self.write_migration_files(changes)
-            if check_changes:
-                sys.exit(1)
 
     def write_to_last_migration_files(self, changes):
         loader = MigrationLoader(connections[DEFAULT_DB_ALIAS])

=== CANDIDATE PATCH
diff --git a/django/core/management/commands/makemigrations.py b/django/core/management/commands/makemigrations.py
--- a/django/core/management/commands/makemigrations.py
+++ b/django/core/management/commands/makemigrations.py
@@ -247,13 +247,15 @@
                         )
                 else:
                     self.log("No changes detected")
+            if check_changes:
+                return
         else:
+            if check_changes:
+                sys.exit(1)
             if self.update:
                 self.write_to_last_migration_files(changes)
             else:
                 self.write_migration_files(changes)
-            if check_changes:
-                sys.exit(1)
 
     def write_to_last_migration_files(self, changes):
         loader = MigrationLoader(connections[DEFAULT_DB_ALIAS])



######## ITEM 1-17: django__django-16116 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/django/core/management/commands/makemigrations.py b/django/core/management/commands/makemigrations.py
--- a/django/core/management/commands/makemigrations.py
+++ b/django/core/management/commands/makemigrations.py
@@ -70,7 +70,10 @@ def add_arguments(self, parser):
             "--check",
             action="store_true",
             dest="check_changes",
-            help="Exit with a non-zero status if model changes are missing migrations.",
+            help=(
+                "Exit with a non-zero status if model changes are missing migrations "
+                "and don't actually write them."
+            ),
         )
         parser.add_argument(
             "--scriptable",
@@ -248,12 +251,12 @@ def handle(self, *app_labels, **options):
                 else:
                     self.log("No changes detected")
         else:
+            if check_changes:
+                sys.exit(1)
             if self.update:
                 self.write_to_last_migration_files(changes)
             else:
                 self.write_migration_files(changes)
-            if check_changes:
-                sys.exit(1)
 
     def write_to_last_migration_files(self, changes):
         loader = MigrationLoader(connections[DEFAULT_DB_ALIAS])

=== CANDIDATE PATCH
diff --git a/django/core/management/commands/makemigrations.py b/django/core/management/commands/makemigrations.py
--- a/django/core/management/commands/makemigrations.py
+++ b/django/core/management/commands/makemigrations.py
@@ -248,12 +248,13 @@
                 else:
                     self.log("No changes detected")
         else:
+            if check_changes:
+                # Exit with a non‑zero status without writing any migration files.
+                sys.exit(1)
             if self.update:
                 self.write_to_last_migration_files(changes)
             else:
                 self.write_migration_files(changes)
-            if check_changes:
-                sys.exit(1)
 
     def write_to_last_migration_files(self, changes):
         loader = MigrationLoader(connections[DEFAULT_DB_ALIAS])



######## ITEM 1-18: django__django-16116 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/django/core/management/commands/makemigrations.py b/django/core/management/commands/makemigrations.py
--- a/django/core/management/commands/makemigrations.py
+++ b/django/core/management/commands/makemigrations.py
@@ -70,7 +70,10 @@ def add_arguments(self, parser):
             "--check",
             action="store_true",
             dest="check_changes",
-            help="Exit with a non-zero status if model changes are missing migrations.",
+            help=(
+                "Exit with a non-zero status if model changes are missing migrations "
+                "and don't actually write them."
+            ),
         )
         parser.add_argument(
             "--scriptable",
@@ -248,12 +251,12 @@ def handle(self, *app_labels, **options):
                 else:
                     self.log("No changes detected")
         else:
+            if check_changes:
+                sys.exit(1)
             if self.update:
                 self.write_to_last_migration_files(changes)
             else:
                 self.write_migration_files(changes)
-            if check_changes:
-                sys.exit(1)
 
     def write_to_last_migration_files(self, changes):
         loader = MigrationLoader(connections[DEFAULT_DB_ALIAS])

=== CANDIDATE PATCH
diff --git a/django/core/management/commands/makemigrations.py b/django/core/management/commands/makemigrations.py
--- a/django/core/management/commands/makemigrations.py
+++ b/django/core/management/commands/makemigrations.py
@@ -248,12 +248,13 @@
                 else:
                     self.log("No changes detected")
         else:
+            if check_changes:
+                # Exit with status 1 to indicate pending migrations, without writing them.
+                sys.exit(1)
             if self.update:
                 self.write_to_last_migration_files(changes)
             else:
                 self.write_migration_files(changes)
-            if check_changes:
-                sys.exit(1)
 
     def write_to_last_migration_files(self, changes):
         loader = MigrationLoader(connections[DEFAULT_DB_ALIAS])



######## ITEM 1-19: django__django-16116 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/django/core/management/commands/makemigrations.py b/django/core/management/commands/makemigrations.py
--- a/django/core/management/commands/makemigrations.py
+++ b/django/core/management/commands/makemigrations.py
@@ -70,7 +70,10 @@ def add_arguments(self, parser):
             "--check",
             action="store_true",
             dest="check_changes",
-            help="Exit with a non-zero status if model changes are missing migrations.",
+            help=(
+                "Exit with a non-zero status if model changes are missing migrations "
+                "and don't actually write them."
+            ),
         )
         parser.add_argument(
             "--scriptable",
@@ -248,12 +251,12 @@ def handle(self, *app_labels, **options):
                 else:
                     self.log("No changes detected")
         else:
+            if check_changes:
+                sys.exit(1)
             if self.update:
                 self.write_to_last_migration_files(changes)
             else:
                 self.write_migration_files(changes)
-            if check_changes:
-                sys.exit(1)
 
     def write_to_last_migration_files(self, changes):
         loader = MigrationLoader(connections[DEFAULT_DB_ALIAS])

=== CANDIDATE PATCH
diff --git a/django/core/management/commands/makemigrations.py b/django/core/management/commands/makemigrations.py
--- a/django/core/management/commands/makemigrations.py
+++ b/django/core/management/commands/makemigrations.py
@@ -247,13 +247,17 @@
                         )
                 else:
                     self.log("No changes detected")
+            # When checking, exit with status 0 (no changes).
+            if check_changes:
+                return
         else:
+            # When checking, exit with status 1 without writing migrations.
+            if check_changes:
+                sys.exit(1)
             if self.update:
                 self.write_to_last_migration_files(changes)
             else:
                 self.write_migration_files(changes)
-            if check_changes:
-                sys.exit(1)
 
     def write_to_last_migration_files(self, changes):
         loader = MigrationLoader(connections[DEFAULT_DB_ALIAS])



######## ITEM 1-20: django__django-16485 (gemma26 s0)
=== GOLD PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -168,7 +168,7 @@ def floatformat(text, arg=-1):
     except (ValueError, OverflowError, InvalidOperation):
         return input_val
 
-    if not m and p < 0:
+    if not m and p <= 0:
         return mark_safe(
             formats.number_format(
                 "%d" % (int(d)),

=== CANDIDATE PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -187,7 +187,7 @@
 
     # Avoid conversion to scientific notation by accessing `sign`, `digits`,
     # and `exponent` from Decimal.as_tuple() directly.
-    rounded_d = d.quantize(exp, ROUND_HALF_UP, Context(prec=prec))
+    rounded_d = d.quantize(exp, ROUND_HALF_UP, Context(prec=max(prec, 1)))
     sign, digits, exponent = rounded_d.as_tuple()
     digits = [str(digit) for digit in reversed(digits)]
     while len(digits) <= abs(exponent):



######## ITEM 1-21: django__django-16485 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -168,7 +168,7 @@ def floatformat(text, arg=-1):
     except (ValueError, OverflowError, InvalidOperation):
         return input_val
 
-    if not m and p < 0:
+    if not m and p <= 0:
         return mark_safe(
             formats.number_format(
                 "%d" % (int(d)),

=== CANDIDATE PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -183,7 +183,7 @@
     tupl = d.as_tuple()
     units = len(tupl[1])
     units += -tupl[2] if m else tupl[2]
-    prec = abs(p) + units + 1
+    prec = max(abs(p) + units + 1, 1)  # Ensure precision is at least 1
 
     # Avoid conversion to scientific notation by accessing `sign`, `digits`,
     # and `exponent` from Decimal.as_tuple() directly.



######## ITEM 1-22: django__django-16485 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -168,7 +168,7 @@ def floatformat(text, arg=-1):
     except (ValueError, OverflowError, InvalidOperation):
         return input_val
 
-    if not m and p < 0:
+    if not m and p <= 0:
         return mark_safe(
             formats.number_format(
                 "%d" % (int(d)),

=== CANDIDATE PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -183,7 +183,7 @@
     tupl = d.as_tuple()
     units = len(tupl[1])
     units += -tupl[2] if m else tupl[2]
-    prec = abs(p) + units + 1
+    prec = max(1, abs(p) + units + 1)
 
     # Avoid conversion to scientific notation by accessing `sign`, `digits`,
     # and `exponent` from Decimal.as_tuple() directly.



######## ITEM 1-23: django__django-16485 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -168,7 +168,7 @@ def floatformat(text, arg=-1):
     except (ValueError, OverflowError, InvalidOperation):
         return input_val
 
-    if not m and p < 0:
+    if not m and p <= 0:
         return mark_safe(
             formats.number_format(
                 "%d" % (int(d)),

=== CANDIDATE PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -184,6 +184,8 @@
     units = len(tupl[1])
     units += -tupl[2] if m else tupl[2]
     prec = abs(p) + units + 1
+    if prec < 1:
+        prec = 1
 
     # Avoid conversion to scientific notation by accessing `sign`, `digits`,
     # and `exponent` from Decimal.as_tuple() directly.



######## ITEM 1-24: django__django-16595 (gemma26 s0)
=== GOLD PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,9 +247,9 @@ def migration_name_fragment(self):
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
-        if isinstance(operation, RemoveField) and self.is_same_field_operation(
-            operation
-        ):
+        if isinstance(
+            operation, (AlterField, RemoveField)
+        ) and self.is_same_field_operation(operation):
             return [operation]
         elif (
             isinstance(operation, RenameField)

=== CANDIDATE PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -252,6 +252,11 @@
         ):
             return [operation]
         elif (
+            isinstance(operation, AlterField)
+            and self.is_same_field_operation(operation)
+        ):
+            return [operation]
+        elif (
             isinstance(operation, RenameField)
             and self.is_same_field_operation(operation)
             and self.field.db_column is None



######## ITEM 1-25: django__django-16595 (gemma26 s2)
=== GOLD PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,9 +247,9 @@ def migration_name_fragment(self):
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
-        if isinstance(operation, RemoveField) and self.is_same_field_operation(
-            operation
-        ):
+        if isinstance(
+            operation, (AlterField, RemoveField)
+        ) and self.is_same_field_operation(operation):
             return [operation]
         elif (
             isinstance(operation, RenameField)

=== CANDIDATE PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,7 +247,11 @@
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
-        if isinstance(operation, RemoveField) and self.is_same_field_operation(
+        if isinstance(operation, AlterField) and self.is_same_field_operation(
+            operation
+        ):
+            return [operation]
+        elif isinstance(operation, RemoveField) and self.is_same_field_operation(
             operation
         ):
             return [operation]



######## ITEM 1-26: django__django-16595 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,9 +247,9 @@ def migration_name_fragment(self):
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
-        if isinstance(operation, RemoveField) and self.is_same_field_operation(
-            operation
-        ):
+        if isinstance(
+            operation, (AlterField, RemoveField)
+        ) and self.is_same_field_operation(operation):
             return [operation]
         elif (
             isinstance(operation, RenameField)

=== CANDIDATE PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,6 +247,9 @@
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
+        # If another AlterField for the same field follows, keep only the later one.
+        if isinstance(operation, AlterField) and self.is_same_field_operation(operation):
+            return [operation]
         if isinstance(operation, RemoveField) and self.is_same_field_operation(
             operation
         ):



######## ITEM 1-27: django__django-16595 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,9 +247,9 @@ def migration_name_fragment(self):
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
-        if isinstance(operation, RemoveField) and self.is_same_field_operation(
-            operation
-        ):
+        if isinstance(
+            operation, (AlterField, RemoveField)
+        ) and self.is_same_field_operation(operation):
             return [operation]
         elif (
             isinstance(operation, RenameField)

=== CANDIDATE PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,6 +247,12 @@
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
+        # If the next operation is another AlterField on the same field,
+        # keep only the later AlterField.
+        if isinstance(operation, AlterField) and self.is_same_field_operation(
+            operation
+        ):
+            return [operation]
         if isinstance(operation, RemoveField) and self.is_same_field_operation(
             operation
         ):



######## ITEM 1-28: django__django-16595 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,9 +247,9 @@ def migration_name_fragment(self):
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
-        if isinstance(operation, RemoveField) and self.is_same_field_operation(
-            operation
-        ):
+        if isinstance(
+            operation, (AlterField, RemoveField)
+        ) and self.is_same_field_operation(operation):
             return [operation]
         elif (
             isinstance(operation, RenameField)

=== CANDIDATE PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,6 +247,11 @@
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
+        # If another AlterField on the same field follows, keep only the later one.
+        if isinstance(operation, AlterField) and self.is_same_field_operation(
+            operation
+        ):
+            return [operation]
         if isinstance(operation, RemoveField) and self.is_same_field_operation(
             operation
         ):



######## ITEM 1-29: django__django-16595 (gpt-oss-20b s0)
=== GOLD PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,9 +247,9 @@ def migration_name_fragment(self):
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
-        if isinstance(operation, RemoveField) and self.is_same_field_operation(
-            operation
-        ):
+        if isinstance(
+            operation, (AlterField, RemoveField)
+        ) and self.is_same_field_operation(operation):
             return [operation]
         elif (
             isinstance(operation, RenameField)

=== CANDIDATE PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -251,6 +251,10 @@
             operation
         ):
             return [operation]
+        elif isinstance(operation, AlterField) and self.is_same_field_operation(
+            operation
+        ):
+            return [operation]
         elif (
             isinstance(operation, RenameField)
             and self.is_same_field_operation(operation)



######## ITEM 1-30: django__django-16595 (gpt-oss-20b s1)
=== GOLD PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,9 +247,9 @@ def migration_name_fragment(self):
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
-        if isinstance(operation, RemoveField) and self.is_same_field_operation(
-            operation
-        ):
+        if isinstance(
+            operation, (AlterField, RemoveField)
+        ) and self.is_same_field_operation(operation):
             return [operation]
         elif (
             isinstance(operation, RenameField)

=== CANDIDATE PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,6 +247,10 @@
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
+        if isinstance(operation, AlterField) and self.is_same_field_operation(
+            operation
+        ):
+            return [operation]
         if isinstance(operation, RemoveField) and self.is_same_field_operation(
             operation
         ):



######## ITEM 1-31: django__django-16595 (gpt-oss-20b s2)
=== GOLD PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -247,9 +247,9 @@ def migration_name_fragment(self):
         return "alter_%s_%s" % (self.model_name_lower, self.name_lower)
 
     def reduce(self, operation, app_label):
-        if isinstance(operation, RemoveField) and self.is_same_field_operation(
-            operation
-        ):
+        if isinstance(
+            operation, (AlterField, RemoveField)
+        ) and self.is_same_field_operation(operation):
             return [operation]
         elif (
             isinstance(operation, RenameField)

=== CANDIDATE PATCH
diff --git a/django/db/migrations/operations/fields.py b/django/db/migrations/operations/fields.py
--- a/django/db/migrations/operations/fields.py
+++ b/django/db/migrations/operations/fields.py
@@ -264,6 +264,8 @@
                     field=self.field,
                 ),
             ]
+        elif isinstance(operation, AlterField) and self.is_same_field_operation(operation):
+            return [operation]
         return super().reduce(operation, app_label)
 
 



######## ITEM 1-32: django__django-16642 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/django/http/response.py b/django/http/response.py
--- a/django/http/response.py
+++ b/django/http/response.py
@@ -609,7 +609,9 @@ def set_headers(self, filelike):
                 # Encoding isn't set to prevent browsers from automatically
                 # uncompressing files.
                 content_type = {
+                    "br": "application/x-brotli",
                     "bzip2": "application/x-bzip",
+                    "compress": "application/x-compress",
                     "gzip": "application/gzip",
                     "xz": "application/x-xz",
                 }.get(encoding, content_type)

=== CANDIDATE PATCH
diff --git a/django/http/response.py b/django/http/response.py
--- a/django/http/response.py
+++ b/django/http/response.py
@@ -612,6 +612,8 @@
                     "bzip2": "application/x-bzip",
                     "gzip": "application/gzip",
                     "xz": "application/x-xz",
+                    "compress": "application/x-compress",
+                    "br": "application/x-brotli",
                 }.get(encoding, content_type)
                 self.headers["Content-Type"] = (
                     content_type or "application/octet-stream"



######## ITEM 1-33: django__django-16877 (gemma26 s0)
=== GOLD PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -444,6 +444,16 @@ def escape_filter(value):
     return conditional_escape(value)
 
 
+@register.filter(is_safe=True)
+def escapeseq(value):
+    """
+    An "escape" filter for sequences. Mark each element in the sequence,
+    individually, as a string that should be auto-escaped. Return a list with
+    the results.
+    """
+    return [conditional_escape(obj) for obj in value]
+
+
 @register.filter(is_safe=True)
 @stringfilter
 def force_escape(value):

=== CANDIDATE PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -496,6 +496,16 @@
     with the results.
     """
     return [mark_safe(obj) for obj in value]
+
+
+@register.filter(is_safe=True)
+def escapeseq(value):
+    """
+    An "escape" filter for sequences. Escape each element in the sequence,
+    individually, after converting them to strings. Return a list
+    with the results.
+    """
+    return [conditional_escape(obj) for obj in value]
 
 
 @register.filter(is_safe=True)



######## ITEM 1-34: django__django-16877 (gemma26 s2)
=== GOLD PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -444,6 +444,16 @@ def escape_filter(value):
     return conditional_escape(value)
 
 
+@register.filter(is_safe=True)
+def escapeseq(value):
+    """
+    An "escape" filter for sequences. Mark each element in the sequence,
+    individually, as a string that should be auto-escaped. Return a list with
+    the results.
+    """
+    return [conditional_escape(obj) for obj in value]
+
+
 @register.filter(is_safe=True)
 @stringfilter
 def force_escape(value):

=== CANDIDATE PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -496,6 +496,16 @@
     with the results.
     """
     return [mark_safe(obj) for obj in value]
+
+
+@register.filter(is_safe=False)
+def escapeseq(value):
+    """
+    An "escape" filter for sequences. Escape each element in the sequence,
+    individually, after converting them to strings. Return a list
+    with the results.
+    """
+    return [conditional_escape(obj) for obj in value]
 
 
 @register.filter(is_safe=True)



######## ITEM 1-35: django__django-16877 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -444,6 +444,16 @@ def escape_filter(value):
     return conditional_escape(value)
 
 
+@register.filter(is_safe=True)
+def escapeseq(value):
+    """
+    An "escape" filter for sequences. Mark each element in the sequence,
+    individually, as a string that should be auto-escaped. Return a list with
+    the results.
+    """
+    return [conditional_escape(obj) for obj in value]
+
+
 @register.filter(is_safe=True)
 @stringfilter
 def force_escape(value):

=== CANDIDATE PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -496,6 +496,13 @@
     with the results.
     """
     return [mark_safe(obj) for obj in value]
+
+@register.filter(is_safe=True)
+def escapeseq(value):
+    """
+    Escape each element in a sequence. Returns a list of escaped strings.
+    """
+    return [conditional_escape(item) for item in value]
 
 
 @register.filter(is_safe=True)



######## ITEM 1-36: django__django-16877 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -444,6 +444,16 @@ def escape_filter(value):
     return conditional_escape(value)
 
 
+@register.filter(is_safe=True)
+def escapeseq(value):
+    """
+    An "escape" filter for sequences. Mark each element in the sequence,
+    individually, as a string that should be auto-escaped. Return a list with
+    the results.
+    """
+    return [conditional_escape(obj) for obj in value]
+
+
 @register.filter(is_safe=True)
 @stringfilter
 def force_escape(value):

=== CANDIDATE PATCH
diff --git a/django/template/defaultfilters.py b/django/template/defaultfilters.py
--- a/django/template/defaultfilters.py
+++ b/django/template/defaultfilters.py
@@ -496,6 +496,16 @@
     with the results.
     """
     return [mark_safe(obj) for obj in value]
+
+
+@register.filter(is_safe=True)
+def escapeseq(value):
+    """
+    Escape each element in the sequence for HTML, similar to ``safeseq`` but
+    applying ``conditional_escape`` to each element. Returns a list of escaped
+    strings, suitable for use with ``join`` when autoescaping is disabled.
+    """
+    return [conditional_escape(obj) for obj in value]
 
 
 @register.filter(is_safe=True)



######## ITEM 1-37: matplotlib__matplotlib-20488 (gpt-oss-120b s0)
=== GOLD PATCH
diff --git a/lib/matplotlib/image.py b/lib/matplotlib/image.py
--- a/lib/matplotlib/image.py
+++ b/lib/matplotlib/image.py
@@ -532,9 +532,9 @@ def _make_image(self, A, in_bbox, out_bbox, clip_bbox, magnification=1.0,
                 # we have re-set the vmin/vmax to account for small errors
                 # that may have moved input values in/out of range
                 s_vmin, s_vmax = vrange
-                if isinstance(self.norm, mcolors.LogNorm):
-                    if s_vmin < 0:
-                        s_vmin = max(s_vmin, np.finfo(scaled_dtype).eps)
+                if isinstance(self.norm, mcolors.LogNorm) and s_vmin <= 0:
+                    # Don't give 0 or negative values to LogNorm
+                    s_vmin = np.finfo(scaled_dtype).eps
                 with cbook._setattr_cm(self.norm,
                                        vmin=s_vmin,
                                        vmax=s_vmax,

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/image.py b/lib/matplotlib/image.py
--- a/lib/matplotlib/image.py
+++ b/lib/matplotlib/image.py
@@ -533,8 +533,12 @@
                 # that may have moved input values in/out of range
                 s_vmin, s_vmax = vrange
                 if isinstance(self.norm, mcolors.LogNorm):
-                    if s_vmin < 0:
-                        s_vmin = max(s_vmin, np.finfo(scaled_dtype).eps)
+                    # Ensure vmin and vmax are finite and positive for LogNorm.
+                    if not np.isfinite(s_vmin) or s_vmin <= 0:
+                        s_vmin = np.finfo(scaled_dtype).eps
+                    if not np.isfinite(s_vmax) or s_vmax <= 0:
+                        # Set vmax to a reasonable value greater than vmin.
+                        s_vmax = max(s_vmin * 10, np.finfo(scaled_dtype).eps)
                 with cbook._setattr_cm(self.norm,
                                        vmin=s_vmin,
                                        vmax=s_vmax,



######## ITEM 1-38: matplotlib__matplotlib-20488 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/lib/matplotlib/image.py b/lib/matplotlib/image.py
--- a/lib/matplotlib/image.py
+++ b/lib/matplotlib/image.py
@@ -532,9 +532,9 @@ def _make_image(self, A, in_bbox, out_bbox, clip_bbox, magnification=1.0,
                 # we have re-set the vmin/vmax to account for small errors
                 # that may have moved input values in/out of range
                 s_vmin, s_vmax = vrange
-                if isinstance(self.norm, mcolors.LogNorm):
-                    if s_vmin < 0:
-                        s_vmin = max(s_vmin, np.finfo(scaled_dtype).eps)
+                if isinstance(self.norm, mcolors.LogNorm) and s_vmin <= 0:
+                    # Don't give 0 or negative values to LogNorm
+                    s_vmin = np.finfo(scaled_dtype).eps
                 with cbook._setattr_cm(self.norm,
                                        vmin=s_vmin,
                                        vmax=s_vmax,

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/image.py b/lib/matplotlib/image.py
--- a/lib/matplotlib/image.py
+++ b/lib/matplotlib/image.py
@@ -533,7 +533,9 @@
                 # that may have moved input values in/out of range
                 s_vmin, s_vmax = vrange
                 if isinstance(self.norm, mcolors.LogNorm):
-                    if s_vmin < 0:
+                    # LogNorm cannot handle non‑positive vmin; ensure it is
+                    # at least the smallest positive float for the dtype.
+                    if s_vmin <= 0:
                         s_vmin = max(s_vmin, np.finfo(scaled_dtype).eps)
                 with cbook._setattr_cm(self.norm,
                                        vmin=s_vmin,



######## ITEM 1-39: matplotlib__matplotlib-20488 (gpt-oss-120b s2)
=== GOLD PATCH
diff --git a/lib/matplotlib/image.py b/lib/matplotlib/image.py
--- a/lib/matplotlib/image.py
+++ b/lib/matplotlib/image.py
@@ -532,9 +532,9 @@ def _make_image(self, A, in_bbox, out_bbox, clip_bbox, magnification=1.0,
                 # we have re-set the vmin/vmax to account for small errors
                 # that may have moved input values in/out of range
                 s_vmin, s_vmax = vrange
-                if isinstance(self.norm, mcolors.LogNorm):
-                    if s_vmin < 0:
-                        s_vmin = max(s_vmin, np.finfo(scaled_dtype).eps)
+                if isinstance(self.norm, mcolors.LogNorm) and s_vmin <= 0:
+                    # Don't give 0 or negative values to LogNorm
+                    s_vmin = np.finfo(scaled_dtype).eps
                 with cbook._setattr_cm(self.norm,
                                        vmin=s_vmin,
                                        vmax=s_vmax,

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/image.py b/lib/matplotlib/image.py
--- a/lib/matplotlib/image.py
+++ b/lib/matplotlib/image.py
@@ -533,8 +533,14 @@
                 # that may have moved input values in/out of range
                 s_vmin, s_vmax = vrange
                 if isinstance(self.norm, mcolors.LogNorm):
-                    if s_vmin < 0:
-                        s_vmin = max(s_vmin, np.finfo(scaled_dtype).eps)
+                    # Ensure vmin/vmax are positive and finite for LogNorm.
+                    eps = np.finfo(scaled_dtype).eps
+                    # Clamp vmin to a small positive number if needed.
+                    if not np.isfinite(s_vmin) or s_vmin <= 0:
+                        s_vmin = eps
+                    # Clamp vmax to a finite positive number if needed.
+                    if not np.isfinite(s_vmax) or s_vmax <= 0:
+                        s_vmax = eps
                 with cbook._setattr_cm(self.norm,
                                        vmin=s_vmin,
                                        vmax=s_vmax,



######## ITEM 1-40: matplotlib__matplotlib-23412 (gpt-oss-120b s1)
=== GOLD PATCH
diff --git a/lib/matplotlib/patches.py b/lib/matplotlib/patches.py
--- a/lib/matplotlib/patches.py
+++ b/lib/matplotlib/patches.py
@@ -586,9 +586,8 @@ def draw(self, renderer):
         # docstring inherited
         if not self.get_visible():
             return
-        # Patch has traditionally ignored the dashoffset.
-        with cbook._setattr_cm(
-                 self, _dash_pattern=(0, self._dash_pattern[1])), \
+
+        with cbook._setattr_cm(self, _dash_pattern=(self._dash_pattern)), \
              self._bind_draw_path_function(renderer) as draw_path:
             path = self.get_path()
             transform = self.get_transform()

=== CANDIDATE PATCH
diff --git a/lib/matplotlib/patches.py b/lib/matplotlib/patches.py
--- a/lib/matplotlib/patches.py
+++ b/lib/matplotlib/patches.py
@@ -549,7 +549,9 @@
         if self._edgecolor[3] == 0 or self._linestyle == 'None':
             lw = 0
         gc.set_linewidth(lw)
-        gc.set_dashes(*self._dash_pattern)
+        # Use the original dash pattern (offset is already in points) so that
+        # the dash offset is honoured for patch edges.
+        gc.set_dashes(*self._unscaled_dash_pattern)
         gc.set_capstyle(self._capstyle)
         gc.set_joinstyle(self._joinstyle)
 



######## ITEM 1-41: matplotlib__matplotlib-24637 (gemma26 s1)
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
@@ -1219,6 +1219,13 @@
 
     zorder = 3
 
+    def set_gid(self, gid):
+        martist.Artist.set_gid(self, gid)
+        if hasattr(self, "patch") and self.patch is not None:
+            self.patch.set_gid(gid)
+        if hasattr(self, "arrow_patch") and self.arrow_patch is not None:
+            self.arrow_patch.set_gid(gid)
+
     def __str__(self):
         return "AnnotationBbox(%g,%g)" % (self.xy[0], self.xy[1])
 



######## ITEM 1-42: matplotlib__matplotlib-24637 (gemma26 s2)
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
@@ -1333,6 +1333,7 @@
             self.patch.set(**bboxprops)
 
         self._internal_update(kwargs)
+        self.patch.set_gid(self.get_gid())
 
     @property
     def xyann(self):
@@ -1400,6 +1401,20 @@
         # docstring inherited
         return Bbox.union([child.get_tightbbox(renderer)
                            for child in self.get_children()])
+
+    def set_gid(self, gid):
+        super().set_gid(gid)
+        if hasattr(self, "patch"):
+            self.patch.set_gid(gid)
+        if hasattr(self, "arrow_patch"):
+            self.arrow_patch.set_gid(gid)
+
+    def set_gid(self, gid):
+        super().set_gid(gid)
+        if hasattr(self, "patch"):
+            self.patch.set_gid(gid)
+        if hasattr(self, "arrow_patch"):
+            self.arrow_patch.set_gid(gid)
 
     def update_positions(self, renderer):
         """



######## ITEM 1-43: matplotlib__matplotlib-24637 (gpt-oss-120b s1)
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
@@ -1401,6 +1401,37 @@
         return Bbox.union([child.get_tightbbox(renderer)
                            for child in self.get_children()])
 
+    def set_gid(self, gid):
+        """Set gid for the AnnotationBbox and propagate it to internal artists.
+
+        This ensures that the gid is honoured by backends (e.g. SVG) that
+        serialize the individual child artists such as the patch, the offsetbox
+        image, and the optional arrow.
+        """
+        super().set_gid(gid)
+
+        # The patch that draws the surrounding box.
+        if hasattr(self, "patch"):
+            self.patch.set_gid(gid)
+
+        # The arrow (if present).
+        if getattr(self, "arrow_patch", None) is not None:
+            self.arrow_patch.set_gid(gid)
+
+        # The contained offsetbox and any of its children (e.g. images).
+        if hasattr(self, "offsetbox"):
+            try:
+                self.offsetbox.set_gid(gid)
+            except Exception:
+                pass
+            for child in getattr(self.offsetbox, "get_children", lambda: [])():
+                try:
+                    child.set_gid(gid)
+                except Exception:
+                    pass
+
+        return self
+
     def update_positions(self, renderer):
         """
         Update pixel positions for the annotated point, the text and the arrow.

