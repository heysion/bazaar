# $Id: conf.py,v 1.32 2004/03/23 13:48:24 wrobell Exp $
#
# Bazaar - an easy to use and powerful abstraction layer between relational
# database and object oriented application.
#
# Copyright (C) 2000-2004 by Artur Wroblewski <wrobell@pld-linux.org>
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

"""
Provides classes for mapping application classes to database relations.

Application class can be defined by standard Python class definition::

    import bazaar.conf

    class Order(bazaar.core.PersistentObject):
        __metaclass__ = bazaar.conf.Persistence
        relation      = 'order'
        columns       = {
            'no'        : bazaar.conf.Column('no'),
            'finished'  : bazaar.conf.Column('finished'),
            'birthdate' : bazaar.conf.Column('birthdate'),
        }

It is possible to create application class by class instantiation::

    Order = bazaar.conf.Persistence('order')
    Order.addColumn('no')
    Order.addColumn('finished')

Of course, both ideas can be mixed::

    class Order(bazaar.core.PersistentObject):
        __metaclass__ = bazaar.conf.Persistence
        relation      = 'order'

    Order.addColumn('no')
    Order.addColumn('finished')

Associations
============
Method L{bazaar.conf.Persistence.addColumn} makes possible to define
associations between classes (see L{bazaar.assoc} module documentation for
implementation details).

One-to-one association
----------------------
To define one-to-one association between two classes, programmer should
specify the application class attribute, relation column and referenced
class. For example, to associate department class with its boss
(uni-directional relationship)::

    Department.addColumn('boss', 'boss_fkey', Boss)

In case of bi-directional association (where boss is aware of department
and vice versa)::

    Department.addColumn('boss', 'boss_fkey', Boss, vattr = 'department')
    Boss.addColumn('department', 'dep_fkey', Department, vattr = 'boss')

Defining bi-directional relationship involves specifing attribute (with
C{vattr} parameter) of opposite class which glues the whole association.

SQL schema of C{Department} and C{Boss} classes would look like::

    create table boss (
        __key__      integer,
        name         varchar(10) not null,
        surname      varchar(20) not null,
        phone        varchar(12) not null,
        dep_fkey     integer unique,
        unique (name, surname),
        primary key (__key__)
        --  see below
        --    foreign key (dep_fkey) references department(__key__) initially deferred
    );
     
     
    create sequence department_seq;
    create table department (
        __key__      integer,
        boss_fkey    integer unique,
        primary key (__key__),
        foreign key (boss_fkey) references boss(__key__) initially deferred
    );

    alter table boss add foreign key (dep_fkey) references department(__key__) initially deferred;


Many-to-many association
------------------------
In relational database many-to-many relationships are created with one
additional link relation. Therefore, when defining the association,
programmer should specify following parameters:
    - attribute name
    - referenced application class
    - link relation and its columns

For example, uni-directional many-to-many association between C{Employee}
and C{Order} classes::

    Employee.addColumn('orders', 'employee', Order, 'employee_orders', 'order')

SQL schema::

    create sequence order_seq;
    create table "order" (
        __key__      integer,
        no           integer not null unique,
        finished     boolean not null,
        primary key (__key__)
    );

    create sequence employee_seq;
    create table employee (
        __key__      integer,
        name         varchar(10) not null,
        surname      varchar(20) not null,
        phone        varchar(12) not null,
        unique (name, surname),
        primary key (__key__)
    );

    create table employee_orders (
        employee         integer,
        "order"          integer,
        primary key (employee, "order"),
        foreign key (employee) references employee(__key__),
        foreign key ("order") references "order"(__key__)
    );


To define bi-directional association attribute of opposite class, as in
case of bi-directional one-to-one association, code should be written::

    Employee.addColumn('orders', 'employee' Order, 'employee_orders', 'order', 'employees')
    Order.addColumn('employees', 'order', Employee, 'employee_orders', 'employee', 'orders')


One-to-many association
-----------------------
Following SQL schema describes two one-to-many associations::

    create sequence article_seq;
    create table article (
        __key__      integer,
        name         varchar(20) not null,
        price        numeric(10,2) not null,
        unique (name),
        primary key (__key__)
    );
     
    create sequence order_item_seq;
    create table order_item (
        __key__      integer,
        order_fkey   integer,
        pos          integer not null,
        article_fkey integer not null,
        quantity     numeric(10,3) not null,
        primary key (__key__),
        unique (order_fkey, pos),
        foreign key (order_fkey) references "order"(__key__),
        foreign key (article_fkey) references article(__key__)
    );

First one is uni-directional relationship between C{Article} and
C{OrderItem} classes' relations - many order items can be created for one
article. The relationship should be defined on "many" side with similar
code as in case of uni-directional one-to-one association::
    
    OrderItem.addColumn('article', 'article_fkey', Article)

There is second relationship. Bi-directional association between C{Order}
and C{OrderItem} classes. The nature of this association due its
realization excludes uni-directionality. It is because of C{order_fkey}
column of C{order_item} relation. Definition of such association considers
its bi-directionality::

    Order.addColumn('items', vcls = OrderItem, vcol = 'order_fkey', vattr = 'order')
    OrderItem.addColumn('order', 'order_fkey', Order, vattr = 'items')

Inheritance
===========
There are two classes defined above. C{Boss} class is very similar to
C{Employee} class. The last one can be reused with inheritance::

    Boss = bazaar.conf.Persistence('Boss', bases = (Employee,), relation = 'boss')

C{Boss} class derives all attributes and associations from C{Employee}
class.

SQL schema for C{Boss} class relation can look like::

    create table boss (
        dep_fkey     integer,
        foreign key (dep_fkey) references department(__key__) initially deferred
    ) inherits(employee);

"""

import logging

import bazaar.core
import bazaar.cache
import bazaar.exc

log = logging.getLogger('bazaar.conf')


class Column:
    """
    Describes application class attribute.

    Application class atribute can be simple attribute or can define
    association (relationship) between application classes.

    When class attribute describes association the C{vcls} is always
    defined. Depedning on relationship type (1-1, 1-n, m-n,
    uni-directional, bi-directional) some of the attributes C{vlink},
    C{vcol}, C{vattr} are defined, too.

    @ivar attr: Application class attribute name.
    @ivar col: Relation column name (equal to C{attr} by default).

    @ivar vcls: Class of referenced object(s).
    @ivar link:  Many-to-many link relation name.
    @ivar vcol: Relation column name of referenced object(s).
    @ivar vattr: Attribute name of referenced object(s). 

    @ivar association: Association descriptor of given column.

    @ivar update: Used with 1-n associations. If true, then update
        referenced objects on relationship update, otherwise add appended
        objects and delete removed objects.

    @ivar is_one_to_one: Class attribute is one-to-one association.
    @ivar is_one_to_many: Class attribute is one-to-many association.
    @ivar is_many_to_many: Class attribute is many-to-many association.
    @ivar is_bidir: Class attribute describes bi-directional association.
    @ivar is_many: Class attribute is one-to-many or many-to-many association.

    @see: bazaar.conf.Persistence.addColumn bazaar.assoc
    """

    def __init__(self, attr, col = None):
        """
        Create application class attribute description.

        @param attr: Application class attribute name.
        @param col: Relation column.
        """
        self.attr = attr

        if col is None:
            self.col = self.attr
        else:
            self.col = col

        self.vcls = None
        self.link = None
        self.vcol = None
        self.vattr = None
        self.association = None
        self.update = True


    is_one_to_one = property(lambda self: \
            self.vcls is not None \
            and self.link is None \
            and self.vcol is None \
    )
    is_one_to_many =  property(lambda self: \
            self.vcls is not None \
            and self.link is None \
            and self.vcol is not None \
            and self.vattr is not None \
    )
    is_many_to_many =  property(lambda self: \
            self.vcls is not None \
            and self.col is not None \
            and self.link is not None \
            and self.vcol is not None \
    )
    is_bidir =  property(lambda self: self.vcls is not None and self.vattr is not None)
    is_many = property(lambda self: self.is_one_to_many or self.is_many_to_many)



class Persistence(type):
    """
    Application class metaclass.

    Programmer defines application classes with the metaclass. The
    class is assigned to the database relation. Class name is used as
    relation name, by default.

    @ivar relation: Database relation name.
    @ivar sequencer: Name of primary key values generator sequencer.
    @ivar columns: List of application class attribute descriptions.
    @ivar cache: Object cache class.
    @ivar defaults: Default values for class attributes.
    """

    def __new__(self, name, bases = (bazaar.core.PersistentObject, ), data = None, relation = None, sequencer = None, modname = __name__):
        """
        Create application class.

        @param relation: Database relation name.
        @param sequencer: Name of primary key values generator sequencer.
        @param modname: Module of the application class, i.e.  C{app.business}.
        """
        if data is None:
            data = {}

        if modname != __name__:
            data['__module__'] = modname

        if relation is None:
            relation = name

        if 'relation' not in data:
            data['relation'] = relation

        if sequencer is None:
            sequencer = '%s_seq' % data['relation']

        if 'sequencer' not in data:
            data['sequencer'] = sequencer

        if 'columns' not in data:
            data['columns'] = {}

        if 'cache' not in data:
            data['cache'] = bazaar.cache.FullObject

        if 'defaults' not in data:
            data['defaults'] = {}

        for c in bases:
            if hasattr(c, 'defaults'):
                data['defaults'].update(c.defaults)

        c = type.__new__(self, name, bases, data)

        if __debug__:
            log.debug('new class "%s" for relation "%s"' % (c.__name__, data['relation']))

        if not c.relation:
            raise bazaar.exc.RelationMappingError('wrong relation name', c)

        setattr(c, '__key__', None)

        return c


    def addColumn(self, attr, col = None, vcls = None, link = None, vcol = None, vattr = None, update = True):
        """
        Add attribute description to persistent application class.

        This way the application class attributes and relationships between
        application classes are defined.

        @param attr: Application class attribute name.
        @param col: Relation column name (equal to C{attr} by default).
        @param vcls: Class of referenced object(s).
        @param link:  Many-to-many link relation name.
        @param vcol: Relation column name of referenced object(s).
        @param vattr: Attribute name of referenced object(s). 
        @param update: Used with 1-n associations. If true, then update
            referenced objects on relationship update, otherwise add appended
            objects and delete removed objects.

        @see: L{bazaar.conf.Column}
        """
        col = Column(attr, col)
        col.vcls = vcls
        col.link = link
        col.vcol = vcol
        col.vattr = vattr
        self.update = update

        col.cache = None

        self.defaults[attr] = None
        if col.is_one_to_one and col.attr != col.col:
            self.defaults[col.col] = None
            

        # set default association buffer
        if col.is_many:
            col.cache = bazaar.cache.FullAssociation

        if not attr:
            raise ColumnMappingError('wrong column name', self, col)

        if attr in self.columns:
            raise bazaar.exc.ColumnMappingError('column is defined', self, col)

        self.columns[col.attr] = col

        if __debug__: log.debug('column "%s" is added to class "%s"' % (attr, self.__name__))


    def getColumns(self):
        """
        Return list of all defined columns including inherited.
        """
        cols = {}

        for cls in self.__bases__:
            if isinstance(cls, Persistence):
                cols.update(cls.getColumns())
        cols.update(self.columns)

        return cols
