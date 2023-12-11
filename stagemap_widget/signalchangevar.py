import inspect

class SignalChangeVar(dict):

    def __get__(self, instance, owner=None):
        who_called = self.caller_id(inspect.currentframe().f_back.f_locals)
        if who_called == 'instance' and self.coord_sys == 'stage':
            # Call from stagemap, so put in map coordinate system
            value = instance.stage_to_map_coord_transform(self)
            self.coord_sys = 'map'
            self.__set__(instance, value)
        elif who_called != 'instance' and self.coord_sys == 'map':
            # Call from outside, so put in stage coords
            value = instance.map_to_stage_coord_transform(self)
            self.coord_sys = 'stage'
            self.__set__(instance, value)

        return self

    def __set__(self, instance, value):
        if 'instance' not in self.__dict__:
            self.instance = instance
            self.coord_sys = 'stage'
            setattr(instance, self.name, value) # initially setting attr
            for k, v in value.items():
                self.__setitem__(k, v)

        who_called = self.caller_id(inspect.currentframe().f_back.f_locals)
        if who_called != 'inside' and who_called != 'instance':
            value = value if self.coord_sys == 'stage' else instance.stage_to_map_coord_transform(value)

        setattr(instance, self.name, value)
        for k, v in value.items():
            self.__setitem__(k, v)

        if who_called != 'inside' and who_called != 'instance':
            self.instance.valueChanged.emit(0)


    def __set_name__(self, owner, name):
        self.name = f"_{name}"


    def __setitem__(self, key, value):
        who_called = self.caller_id(inspect.currentframe().f_back.f_locals)
        super(SignalChangeVar, self).__setitem__(key, value)
        if who_called != 'inside' and who_called != 'instance':
            self.instance.valueChanged.emit(0)

    def caller_id(self, locals):
        """Identify if function was called from StageMap or outside"""
        # If function called from StageMap
        if locals.get('self', None) is self.instance:
            return 'instance'
        elif locals.get('self', None) is self:
            return 'inside'
        # else, outside call
        else:
            return locals.get('self', None)